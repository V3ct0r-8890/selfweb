<!-- 
  Program: Robust Single File RSS Feed Reader (v7)
  Created: 2025-12-02 22:20:00 (Bangkok Time)
  
  Specifications:
  1. Input: URL field + Presets dropdown (Updated list per user request).
  2. Logic: Uses Multi-Proxy Fallback (AllOrigins -> CORSProxy.io).
  3. Parsing: Handles RSS 2.0, Atom, RDF + Base64 decoding.
  4. Frame View: Preview website in iframe.
  5. Reliability: Fixes 408 Timeouts by switching proxies automatically.
  
  Usage:
  - Open in browser.
  - Load a feed.
  - If primary server times out, it auto-retries with backup.
-->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RSS Feed Reader v7 (Multi-Proxy)</title>
    <style>
        :root {
            --bg-color: #f4f4f9;
            --sidebar-bg: #ffffff;
            --header-bg: #2c3e50;
            --text-color: #333;
            --accent-color: #e74c3c;
            --hover-color: #ecf0f1;
            --border-color: #ddd;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: var(--bg-color);
            color: var(--text-color);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        /* --- Header --- */
        header {
            background-color: var(--header-bg);
            padding: 15px 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            z-index: 10;
        }

        select, input[type="text"] {
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #555;
            background-color: #34495e;
            color: white;
            font-size: 14px;
            outline: none;
        }

        input[type="text"] {
            flex-grow: 1;
            background-color: #fff;
            color: #333;
            border-color: white;
        }

        button {
            padding: 10px 20px;
            background-color: var(--accent-color);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 13px;
            transition: background 0.2s;
        }

        button:hover {
            background-color: #c0392b;
        }

        /* --- Main Layout --- */
        #main-container {
            display: flex;
            flex: 1;
            height: calc(100vh - 70px);
        }

        /* --- Sidebar --- */
        #sidebar {
            width: 350px;
            background-color: var(--sidebar-bg);
            border-right: 1px solid var(--border-color);
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }

        .feed-item {
            padding: 15px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
        }

        .feed-item:hover {
            background-color: var(--hover-color);
        }

        .feed-item.active {
            background-color: #fff0ef;
            border-left: 4px solid var(--accent-color);
        }

        .item-date {
            font-size: 0.75em;
            color: #888;
            margin-bottom: 5px;
            display: block;
        }

        .item-title {
            font-weight: 600;
            font-size: 0.95em;
            color: #2c3e50;
            line-height: 1.4;
        }

        /* --- Content Area --- */
        #content-area {
            flex: 1;
            background-color: white;
            position: relative;
            overflow: hidden; 
            display: flex;
            flex-direction: column;
        }

        /* Standard Article View */
        .article-view {
            padding: 40px;
            overflow-y: auto;
            height: 100%;
        }

        .article-view h1 {
            color: #2c3e50;
            border-bottom: 2px solid var(--accent-color);
            padding-bottom: 15px;
            margin-top: 0;
        }

        .article-content {
            font-size: 1.1em;
            line-height: 1.8;
            color: #444;
            max-width: 800px;
        }

        .article-content img {
            max-width: 100%;
            height: auto;
            border-radius: 5px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin: 10px 0;
        }

        /* Frame Preview Mode */
        .preview-container {
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        .preview-header {
            background-color: #ecf0f1;
            padding: 10px 20px;
            border-bottom: 1px solid #ccc;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .preview-warning {
            background-color: #fff3cd;
            color: #856404;
            padding: 8px 20px;
            font-size: 0.85em;
            border-bottom: 1px solid #ffeeba;
        }

        iframe.web-frame {
            border: none;
            flex: 1;
            width: 100%;
            background-color: #fff;
        }

        .btn-secondary {
            background-color: #95a5a6;
            margin-left: 10px;
        }
        .btn-secondary:hover { background-color: #7f8c8d; }

        .btn-primary {
            background-color: var(--accent-color);
        }

        /* --- Utility --- */
        .msg-box {
            padding: 40px;
            text-align: center;
            color: #777;
        }
        
        .error-box {
            background-color: #ffeaea;
            color: #c0392b;
            padding: 20px;
            border-radius: 5px;
            border: 1px solid #ffcccc;
            margin: 20px;
            font-family: monospace;
            white-space: pre-wrap;
            text-align: left;
            word-break: break-all;
        }

        .loader {
            border: 4px solid #f3f3f3;
            border-top: 4px solid var(--accent-color);
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }

        .status-text {
            font-size: 0.9em;
            color: #666;
            margin-top: 10px;
        }

        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>

    <header>
        <select id="presetSelect" onchange="usePreset()">
            <option value="">-- Select a Preset Feed --</option>
            <option value="http://www.blognone.com/atom.xml">Blognone</option>
            <option value="https://droidsans.com/feed/">DroidSans</option>
            <option value="http://www.macrumors.com/macrumors.xml">MacRumors</option>
            <option value="http://www.dpreview.com/feeds/news.xml">DPReview</option>
            <option value="https://brandinside.asia/feed/">Brand Inside</option>
            <option value="https://www.bleepingcomputer.com/feed/">BleepingComputer</option>
        </select>
        <input type="text" id="feedUrl" placeholder="Or enter RSS URL here..." value="http://www.blognone.com/atom.xml">
        <button id="loadBtn" onclick="fetchFeed()">Load Feed</button>
    </header>

    <div id="main-container">
        <aside id="sidebar">
            <div class="msg-box" style="padding:20px;">Ready to load.</div>
        </aside>
        
        <main id="content-area">
            <div class="msg-box">
                <h2>RSS Reader v7</h2>
                <p>Select a topic on the left to read.</p>
            </div>
        </main>
    </div>

    <script>
        let currentFeedItems = [];
        let selectedIndex = -1;

        function usePreset() {
            const select = document.getElementById('presetSelect');
            const input = document.getElementById('feedUrl');
            if(select.value) {
                input.value = select.value;
                fetchFeed();
            }
        }

        function updateSidebarStatus(msg) {
            const sidebar = document.getElementById('sidebar');
            sidebar.innerHTML = `
                <div class="loader"></div>
                <div style="text-align:center" class="status-text">${msg}</div>
            `;
        }

        async function fetchFeed() {
            const url = document.getElementById('feedUrl').value.trim();
            const sidebar = document.getElementById('sidebar');
            const contentArea = document.getElementById('content-area');
            const btn = document.getElementById('loadBtn');

            if (!url) return alert("Please enter a URL");

            // UI Reset
            btn.disabled = true;
            contentArea.innerHTML = '<div class="msg-box">Waiting for selection...</div>';
            currentFeedItems = [];
            selectedIndex = -1;

            try {
                let rawContent = "";

                // --- ATTEMPT 1: AllOrigins (Preferred) ---
                try {
                    updateSidebarStatus("Connecting to primary server...");
                    const proxyUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(url)}`;
                    
                    // Set a timeout specifically for the fetch to avoid hanging indefinitely
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10s timeout
                    
                    const response = await fetch(proxyUrl, { signal: controller.signal });
                    clearTimeout(timeoutId);

                    if (!response.ok) throw new Error(`Status ${response.status}`);
                    
                    const data = await response.json();
                    if (!data.contents) throw new Error("Empty contents");
                    
                    rawContent = data.contents; // AllOrigins wraps content in JSON

                } catch (primaryError) {
                    console.warn("Primary proxy failed:", primaryError);
                    
                    // --- ATTEMPT 2: CORSProxy.io (Backup) ---
                    updateSidebarStatus("Primary failed (Timeout/Error).<br>Retrying with backup server...");
                    
                    // CORSProxy.io returns the raw text directly, not wrapped in JSON
                    const backupUrl = `https://corsproxy.io/?${encodeURIComponent(url)}`;
                    const response = await fetch(backupUrl);
                    
                    if (!response.ok) throw new Error(`Backup server failed with Status ${response.status}`);
                    
                    rawContent = await response.text();
                }

                // Decode Base64 if needed (common with proxies)
                rawContent = decodeProxyContent(rawContent);

                // DEBUG CHECK: Is it actually XML?
                const trimmedContent = rawContent.trim();
                if (trimmedContent.toLowerCase().startsWith('<!doctype html') || trimmedContent.toLowerCase().startsWith('<html')) {
                    const match = trimmedContent.match(/<title>(.*?)<\/title>/i);
                    const titleInfo = match ? `(Title: ${match[1]})` : "";
                    throw new Error(`The URL returned a Webpage (HTML), not an RSS Feed (XML). ${titleInfo}`);
                }

                parseXML(rawContent);

            } catch (err) {
                renderError(err);
            } finally {
                btn.disabled = false;
            }
        }

        function decodeProxyContent(content) {
            const trimmed = content.trim();
            if (trimmed.startsWith("data:")) {
                const commaIndex = trimmed.indexOf(",");
                if (commaIndex !== -1) {
                    const base64Data = trimmed.substring(commaIndex + 1);
                    try {
                        const binaryString = atob(base64Data);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {
                            bytes[i] = binaryString.charCodeAt(i);
                        }
                        const decoder = new TextDecoder('utf-8');
                        return decoder.decode(bytes);
                    } catch (e) {
                        return content; 
                    }
                }
            }
            return content;
        }

        function parseXML(xmlString) {
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(xmlString, "text/xml");
            
            const parseError = xmlDoc.querySelector('parsererror');
            if (parseError) {
                const snippet = xmlString.substring(0, 200).replace(/</g, "&lt;");
                throw new Error(`XML Parsing Failed. Snippet:\n${snippet}...\n\nInner Error: ${parseError.textContent}`);
            }

            let items = [];
            const rssItems = xmlDoc.querySelectorAll("item");
            const atomEntries = xmlDoc.querySelectorAll("entry");

            if (rssItems.length > 0) {
                items = Array.from(rssItems).map(node => parseRSSItem(node));
            } else if (atomEntries.length > 0) {
                items = Array.from(atomEntries).map(node => parseAtomEntry(node));
            } else {
                throw new Error("No <item> or <entry> tags found in the XML.");
            }

            currentFeedItems = items;
            renderSidebar(items);
        }

        function parseRSSItem(node) {
            return {
                title: getChildText(node, "title"),
                link: getChildText(node, "link"),
                date: getChildText(node, "pubDate") || getChildText(node, "dc:date"),
                content: getChildText(node, "content:encoded") || 
                         getChildText(node, "description") || 
                         "No content."
            };
        }

        function parseAtomEntry(node) {
            const linkNode = node.querySelector("link");
            const link = linkNode ? linkNode.getAttribute("href") : "";

            return {
                title: getChildText(node, "title"),
                link: link,
                date: getChildText(node, "updated") || getChildText(node, "published"),
                content: getChildText(node, "content") || 
                         getChildText(node, "summary") || 
                         "No content."
            };
        }

        function getChildText(parent, tagName) {
            const node = parent.getElementsByTagName(tagName)[0];
            if (!node && tagName.includes(":")) {
                const [prefix, localName] = tagName.split(":");
                const collections = parent.getElementsByTagName("*");
                for (let i = 0; i < collections.length; i++) {
                    if (collections[i].nodeName === tagName || collections[i].localName === localName) {
                        return collections[i].textContent.trim();
                    }
                }
            }
            return node ? node.textContent.trim() : "";
        }

        function renderSidebar(items) {
            const sidebar = document.getElementById('sidebar');
            sidebar.innerHTML = "";

            if (items.length === 0) {
                sidebar.innerHTML = '<div class="msg-box">No items found.</div>';
                return;
            }

            items.forEach((item, index) => {
                const div = document.createElement('div');
                div.className = 'feed-item';
                div.onclick = () => showContent(index);

                let dateStr = item.date;
                try { if (dateStr) dateStr = new Date(dateStr).toLocaleDateString(); } catch(e) {}

                div.innerHTML = `
                    <span class="item-date">${dateStr || ''}</span>
                    <div class="item-title">${item.title}</div>
                `;
                sidebar.appendChild(div);
            });
        }

        function showContent(index) {
            selectedIndex = index;
            const item = currentFeedItems[index];
            const contentArea = document.getElementById('content-area');
            
            document.querySelectorAll('.feed-item').forEach(d => d.classList.remove('active'));
            if(document.querySelectorAll('.feed-item')[index]) {
                document.querySelectorAll('.feed-item')[index].classList.add('active');
            }

            // Normal Article View
            contentArea.innerHTML = `
                <div class="article-view">
                    <h1>${item.title}</h1>
                    <div style="color:#666; margin-bottom:20px;">
                        ${item.date ? new Date(item.date).toLocaleString() : ''}
                    </div>
                    <div class="article-content">
                        ${item.content}
                    </div>
                    <div style="margin-top:40px; padding-top:20px; border-top:1px solid #ddd;">
                        <p style="margin-bottom:10px; color:#555;"><strong>Option 1:</strong> View original site inside this window:</p>
                        <button class="btn-primary" onclick="openPreview('${item.link}')">Preview Website</button>
                        
                        <p style="margin-top:20px; margin-bottom:10px; color:#555;"><strong>Option 2:</strong> Open in new browser tab:</p>
                        <a href="${item.link}" target="_blank" style="color:var(--accent-color); text-decoration:underline;">Open in New Tab &rarr;</a>
                    </div>
                </div>
            `;
        }

        function openPreview(url) {
            if(!url) return alert("No URL available for this item.");
            
            const contentArea = document.getElementById('content-area');
            
            contentArea.innerHTML = `
                <div class="preview-container">
                    <div class="preview-header">
                        <strong>Previewing:</strong>
                        <div>
                            <button class="btn-secondary" onclick="closePreview()">Close Preview</button>
                            <a href="${url}" target="_blank" style="margin-left:10px; color:var(--accent-color);">Open in New Tab</a>
                        </div>
                    </div>
                    <div class="preview-warning">
                        <strong>Note:</strong> If the area below is blank or shows an error, the website (${new URL(url).hostname}) blocks embedded frames for security. Please use "Open in New Tab".
                    </div>
                    <iframe src="${url}" class="web-frame" title="Article Preview"></iframe>
                </div>
            `;
        }

        function closePreview() {
            if(selectedIndex > -1) {
                showContent(selectedIndex);
            } else {
                document.getElementById('content-area').innerHTML = '<div class="msg-box">Select a topic.</div>';
            }
        }

        function renderError(error) {
            const sidebar = document.getElementById('sidebar');
            sidebar.innerHTML = '';
            const errDiv = document.createElement('div');
            errDiv.className = 'error-box';
            errDiv.innerHTML = `<strong>Error:</strong><br>${error.message}`;
            sidebar.appendChild(errDiv);
            document.getElementById('content-area').innerHTML = '';
        }
    </script>
</body>
</html>
