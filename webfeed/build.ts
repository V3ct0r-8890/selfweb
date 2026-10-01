/*
 * Web Feed builder (prototype) — turns normal web pages into feed items with our own code.
 *
 * Runs in GitHub Actions on a schedule (and by hand: `node webfeed/build.ts`), where the
 * browser's cross-site rule does not apply. Writes feeds/web/<id>.json and feeds/web/index.json,
 * which GitHub Pages then serves from the app's own address. No third-party service is used.
 *
 * Node 24 runs this file directly (type stripping), so there are no npm dependencies.
 * For each site, in order:
 *   1. the page's own RSS/Atom link (<link rel="alternate">), parsed here
 *   2. structured data on the page (JSON-LD NewsArticle / ItemList)
 *   3. article-looking links on the page (headline text + article-shaped URL)
 * Items without a date get the time this job first saw them, kept between runs.
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises';

interface Site { id: string; name: string; url: string; }
interface Item { title: string; link: string; date: string; summary: string; image: string; }
interface SiteFeed { id: string; name: string; url: string; method: string; generated: string; error?: string; items: Item[]; }

const ROOT = new URL('../', import.meta.url);
const OUT_DIR = new URL('feeds/web/', ROOT);
const MAX_ITEMS = 40;
const TIMEOUT_MS = 20000;
const UA = 'Mozilla/5.0 (compatible; selfweb-webfeed/0.1; +https://v3ct0r-8890.github.io/selfweb/)';

// ---------- small HTML/XML helpers (no DOM in Node, so these are deliberately simple) ----------
const ENTITIES: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };

function decodeEntities(s: string): string {
    return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e: string) => {
        if (e[0] === '#') {
            const code = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
            return Number.isFinite(code) && code > 0 && code < 0x110000 ? String.fromCodePoint(code) : m;
        }
        return ENTITIES[e.toLowerCase()] ?? m;
    });
}

function stripCdata(s: string): string {
    return s.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1');
}

// Plain text only: the viewer never renders HTML from these files.
function toText(html: string, max = 0): string {
    const t = decodeEntities(stripCdata(html)
        .replace(/<(script|style|noscript)[\s\S]*?<\/\1>/gi, ' ')
        .replace(/<[^>]+>/g, ' '))
        .replace(/\s+/g, ' ').trim();
    return max && t.length > max ? t.slice(0, max - 1).trimEnd() + '…' : t;
}

function attr(tag: string, name: string): string {
    const m = tag.match(new RegExp(`\\b${name}\\s*=\\s*("([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i'));
    return m ? decodeEntities(m[2] ?? m[3] ?? m[4] ?? '') : '';
}

function absUrl(href: string, base: string): string {
    if (!href.trim()) return ''; // new URL('', base) would silently become the page itself
    try {
        const u = new URL(href.trim(), base);
        return u.protocol === 'http:' || u.protocol === 'https:' ? u.href : '';
    } catch { return ''; }
}

function isoDate(s: string): string {
    if (!s) return '';
    const d = new Date(s.trim());
    return isNaN(d.getTime()) ? '' : d.toISOString();
}

async function get(url: string): Promise<{ text: string; type: string; finalUrl: string }> {
    const res = await fetch(url, {
        headers: { 'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' },
        redirect: 'follow',
        signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    return { text: await res.text(), type: res.headers.get('content-type') ?? '', finalUrl: res.url || url };
}

// ---------- 1. RSS / Atom ----------
function findFeedLink(html: string, base: string): string {
    for (const tag of html.match(/<link\b[^>]*>/gi) ?? []) {
        const rel = attr(tag, 'rel').toLowerCase();
        const type = attr(tag, 'type').toLowerCase();
        if (rel.split(/\s+/).includes('alternate') && /(rss|atom)\+xml/.test(type)) {
            const href = absUrl(attr(tag, 'href'), base);
            if (href) return href;
        }
    }
    return '';
}

function tagText(block: string, name: string): string {
    const m = block.match(new RegExp(`<${name}\\b[^>]*>([\\s\\S]*?)<\\/${name}>`, 'i'));
    return m ? stripCdata(m[1]).trim() : '';
}

function parseFeedXml(xml: string, base: string): Item[] {
    const blocks = xml.match(/<item\b[\s\S]*?<\/item>/gi) ?? xml.match(/<entry\b[\s\S]*?<\/entry>/gi) ?? [];
    return blocks.map((b) => {
        // RSS <link>url</link>; Atom <link href="..." rel="alternate"/>
        let link = toText(tagText(b, 'link'));
        if (!link) {
            const links = b.match(/<link\b[^>]*>/gi) ?? [];
            const alt = links.find((l) => !attr(l, 'rel') || attr(l, 'rel') === 'alternate') ?? links[0] ?? '';
            link = attr(alt, 'href');
        }
        // RSS <enclosure url>/<media:*>, or Atom <link rel="enclosure" href>
        const media = (b.match(/<(media:content|media:thumbnail|enclosure)\b[^>]*>/i) ?? [''])[0]
            || ((b.match(/<link\b[^>]*>/gi) ?? []).find((l) => attr(l, 'rel') === 'enclosure') ?? '');
        const mediaType = attr(media, 'type');
        return {
            title: toText(tagText(b, 'title'), 300),
            link: absUrl(link, base),
            date: isoDate(tagText(b, 'pubDate') || tagText(b, 'published') || tagText(b, 'updated') || tagText(b, 'dc:date')),
            summary: toText(tagText(b, 'description') || tagText(b, 'summary') || tagText(b, 'content:encoded') || tagText(b, 'content'), 400),
            image: !mediaType || mediaType.startsWith('image/') ? absUrl(attr(media, 'url') || attr(media, 'href'), base) : '',
        };
    }).filter((i) => i.title && i.link);
}

// ---------- 2. JSON-LD ----------
function parseJsonLd(html: string, base: string): Item[] {
    const items: Item[] = [];
    const visit = (node: unknown): void => {
        if (!node || typeof node !== 'object') return;
        if (Array.isArray(node)) { node.forEach(visit); return; }
        const o = node as Record<string, unknown>;
        const type = ([] as unknown[]).concat(o['@type'] ?? []).map(String);
        if (type.some((t) => /Article|BlogPosting|NewsArticle|Report/.test(t)) && (o.headline || o.name)) {
            const img = o.image as unknown;
            const imgUrl = typeof img === 'string' ? img
                : Array.isArray(img) ? String((img[0] as Record<string, unknown>)?.url ?? img[0] ?? '')
                : String((img as Record<string, unknown> | undefined)?.url ?? '');
            items.push({
                title: toText(String(o.headline ?? o.name), 300),
                link: absUrl(String(o.url ?? (o.mainEntityOfPage as Record<string, unknown>)?.['@id'] ?? o.mainEntityOfPage ?? ''), base),
                date: isoDate(String(o.datePublished ?? o.dateModified ?? '')),
                summary: toText(String(o.description ?? ''), 400),
                image: absUrl(imgUrl, base),
            });
        }
        if (o.itemListElement) visit(o.itemListElement);
        if (o.item) visit(o.item);
        if (o['@graph']) visit(o['@graph']);
    };
    for (const m of html.matchAll(/<script\b[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
        try { visit(JSON.parse(m[1].trim())); }
        catch { /* malformed block on the site: skip it, others may still parse */ }
    }
    return items.filter((i) => i.title && i.link);
}

// ---------- 3. Article-looking links ----------
function looksLikeArticle(u: URL, page: URL): boolean {
    if (u.hostname.replace(/^www\./, '') !== page.hostname.replace(/^www\./, '')) return false;
    const path = u.pathname.replace(/\/+$/, '');
    if (!path || path === page.pathname.replace(/\/+$/, '')) return false;
    if (/\/(tag|tags|category|categories|author|page|search|login|about|contact|privacy)(\/|$)/i.test(path)) return false;
    const segs = path.split('/').filter(Boolean);
    const last = segs[segs.length - 1] ?? '';
    // Article URLs usually carry an id or date, or a long hyphenated slug.
    return /\d{3,}/.test(path) || (last.split('-').length >= 4) || segs.length >= 3;
}

// First real picture in a card: lazy-loading pages put a placeholder in src and the
// real image in srcset or data-src, so those are read too and placeholders skipped.
function pickImage(fragment: string, base: string): string {
    for (const [tag] of fragment.matchAll(/<img\b[^>]*>/gi)) {
        const srcset = attr(tag, 'srcset') || attr(tag, 'data-srcset');
        const candidates = [attr(tag, 'data-src'), srcset.split(',')[0]?.trim().split(/\s+/)[0] ?? '', attr(tag, 'src')];
        for (const c of candidates) {
            if (!c || /placeholder|spacer|blank|transparent|^data:/i.test(c)) continue;
            const url = absUrl(c, base);
            if (url) return url;
        }
    }
    return '';
}

function parseLinks(html: string, base: string): Item[] {
    const page = new URL(base);
    const body = html.replace(/<(script|style|noscript|nav|footer|header)\b[\s\S]*?<\/\1>/gi, ' ');
    const seen = new Set<string>();
    const items: Item[] = [];
    for (const m of body.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)) {
        const link = absUrl(attr(`<a ${m[1]}>`, 'href'), base);
        if (!link || seen.has(link)) continue;
        let u: URL;
        try { u = new URL(link); } catch { continue; }
        u.hash = '';
        // Cards often wrap a heading plus a teaser in one link: the heading is the title.
        const heading = m[2].match(/<h[1-6]\b[^>]*>([\s\S]*?)<\/h[1-6]>/i);
        const title = toText(heading ? heading[1] : m[2], 300) || toText(attr(`<a ${m[1]}>`, 'title'), 300);
        const teaser = heading ? toText(m[2].replace(heading[0], ' '), 400) : '';
        // Headlines are sentences, not "Read more" or a single word.
        if (title.length < 20 || title.split(/\s+/).length < 3 && !/[฀-๿぀-鿿]/.test(title)) continue;
        if (!looksLikeArticle(u, page)) continue;
        seen.add(link);
        // A <time datetime> right after the link usually belongs to the same card.
        const after = body.slice(m.index! + m[0].length, m.index! + m[0].length + 600);
        const time = (after.match(/<time\b[^>]*>/i) ?? [''])[0];
        items.push({ title, link: u.href, date: isoDate(attr(time, 'datetime')), summary: teaser, image: pickImage(m[2], base) });
        if (items.length >= MAX_ITEMS) break;
    }
    return items;
}

// ---------- per site ----------
async function buildSite(site: Site, previous: Map<string, string>, now: string): Promise<SiteFeed> {
    const feed: SiteFeed = { id: site.id, name: site.name, url: site.url, method: '', generated: now, items: [] };
    try {
        const page = await get(site.url);
        let items: Item[] = [];
        if (/xml|rss|atom/i.test(page.type) || /^\s*<\?xml|<rss\b|<feed\b/i.test(page.text.slice(0, 500))) {
            items = parseFeedXml(page.text, page.finalUrl); feed.method = 'rss (given url)';
        }
        const feedLink = items.length ? '' : findFeedLink(page.text, page.finalUrl);
        if (feedLink) {
            try {
                items = parseFeedXml((await get(feedLink)).text, feedLink);
                feed.method = `rss (found ${feedLink})`;
            } catch (e) { console.warn(`[${site.id}] feed link failed, falling back:`, (e as Error).message); }
        }
        if (!items.length) {
            // Structured data often describes only the page itself; ignore that entry.
            const pageUrl = page.finalUrl.replace(/\/+$/, '');
            const ld = parseJsonLd(page.text, page.finalUrl).filter((i) => i.link.replace(/\/+$/, '') !== pageUrl);
            const links = parseLinks(page.text, page.finalUrl);
            [items, feed.method] = ld.length >= 3 && ld.length >= links.length / 2 ? [ld, 'json-ld'] : [links, 'page links'];
        }
        if (!items.length) feed.method = 'none found';

        const seen = new Set<string>();
        feed.items = items.filter((i) => !seen.has(i.link) && seen.add(i.link)).slice(0, MAX_ITEMS).map((i) => ({
            ...i,
            // No date on the page: use when we first saw it, so the Days filter still works.
            date: i.date || previous.get(i.link) || now,
        }));
    } catch (e) {
        feed.error = (e as Error).message;
        feed.method = 'failed';
        console.error(`[${site.id}] ${feed.error}`);
    }
    return feed;
}

async function readPrevious(id: string): Promise<{ dates: Map<string, string>; feed: SiteFeed | null }> {
    try {
        const feed = JSON.parse(await readFile(new URL(`${id}.json`, OUT_DIR), 'utf8')) as SiteFeed;
        return { dates: new Map(feed.items.map((i) => [i.link, i.date])), feed };
    } catch { return { dates: new Map(), feed: null }; } // first run for this site
}

async function main(): Promise<void> {
    const sites = JSON.parse(await readFile(new URL('webfeed/sites.json', ROOT), 'utf8')) as Site[];
    await mkdir(OUT_DIR, { recursive: true });
    const now = new Date().toISOString();
    const index: Array<Omit<SiteFeed, 'items'> & { count: number }> = [];

    for (const site of sites) {
        if (!/^[a-z0-9-]+$/.test(site.id)) { console.error(`skipping site with bad id: ${site.id}`); continue; }
        const prev = await readPrevious(site.id);
        let feed = await buildSite(site, prev.dates, now);
        // A failed run keeps the last good items rather than emptying the feed.
        if (feed.error && prev.feed?.items.length) feed = { ...feed, items: prev.feed.items };
        await writeFile(new URL(`${site.id}.json`, OUT_DIR), JSON.stringify(feed, null, 1) + '\n');
        const { items, ...meta } = feed;
        index.push({ ...meta, count: items.length });
        console.log(`[${site.id}] ${feed.method}: ${items.length} items${feed.error ? ' (error: ' + feed.error + ')' : ''}`);
    }
    await writeFile(new URL('index.json', OUT_DIR), JSON.stringify({ generated: now, sites: index }, null, 1) + '\n');
}

main().catch((e) => { console.error(e); process.exit(1); });
