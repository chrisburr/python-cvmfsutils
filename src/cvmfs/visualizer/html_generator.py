# -*- coding: utf-8 -*-
"""
HTML generator for CVMFS catalog visualization.

Generates a self-contained HTML file with an interactive canvas-based sunburst chart.
"""

import json
from .tree_builder import CatalogNode

# D3.js CDN URL (used for hierarchy/partition layout only, not rendering)
D3_CDN = "https://d3js.org/d3.v7.min.js"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CVMFS Catalog Visualizer - {repo_name}</title>
    <script src="{d3_cdn}"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        header {{
            background: #16213e;
            padding: 1rem 2rem;
            border-bottom: 1px solid #0f3460;
        }}

        header h1 {{
            font-size: 1.5rem;
            font-weight: 500;
        }}

        header .repo-name {{
            color: #e94560;
            font-family: monospace;
        }}

        .container {{
            display: flex;
            flex: 1;
            overflow: hidden;
        }}

        .chart-container {{
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 1rem;
            max-height: calc(100vh - 60px);
            position: relative;
        }}

        #chart {{
            max-width: min(80vh, 800px);
            max-height: 80vh;
        }}

        .sidebar {{
            width: 350px;
            background: #16213e;
            padding: 1.5rem;
            overflow-y: auto;
            border-left: 1px solid #0f3460;
        }}

        .sidebar h2 {{
            font-size: 1rem;
            font-weight: 500;
            margin-bottom: 1rem;
            color: #e94560;
        }}

        .info-panel {{
            background: #1a1a2e;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }}

        .info-row {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #0f3460;
        }}

        .info-row:last-child {{
            border-bottom: none;
        }}

        .info-label {{
            color: #888;
            font-size: 0.85rem;
        }}

        .info-value {{
            font-family: monospace;
            font-size: 0.9rem;
        }}

        .info-value.hash {{
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            cursor: pointer;
        }}
        .info-value.hash:hover {{
            color: #e94560;
        }}

        .legend {{
            position: absolute;
            bottom: 1rem;
            right: 1rem;
            background: rgba(22, 33, 62, 0.9);
            padding: 0.75rem 1rem;
            border-radius: 8px;
            border: 1px solid #0f3460;
        }}

        .legend-title {{
            font-size: 0.75rem;
            color: #e94560;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 0.35rem;
            font-size: 0.75rem;
        }}

        .legend-item:last-child {{
            margin-bottom: 0;
        }}

        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
            margin-right: 0.5rem;
            flex-shrink: 0;
        }}

        #large-badge {{
            min-height: 1.75rem;
            margin-top: 0.5rem;
        }}

        .large-indicator {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            background: #e94560;
            border-radius: 4px;
            font-size: 0.75rem;
        }}

        .stats {{
            font-size: 0.8rem;
            color: #888;
            margin-top: 1rem;
        }}

        .instructions {{
            font-size: 0.8rem;
            color: #666;
            margin-top: 1rem;
            line-height: 1.5;
        }}

        .tips {{
            font-size: 0.8rem;
            color: #888;
            margin-top: 1rem;
            line-height: 1.5;
        }}
        .tips strong {{
            color: #e94560;
        }}
        .command-box {{
            background: #1a1a2e;
            border: 1px solid #0f3460;
            border-radius: 4px;
            padding: 0.5rem;
            margin-top: 0.5rem;
            font-family: monospace;
            font-size: 0.75rem;
            word-break: break-all;
            cursor: pointer;
            position: relative;
        }}
        .command-box:hover {{
            border-color: #e94560;
        }}
        .command-box::after {{
            content: "click to copy";
            position: absolute;
            right: 0.5rem;
            top: 50%;
            transform: translateY(-50%);
            font-size: 0.65rem;
            color: #666;
        }}
        .command-box:hover::after {{
            color: #e94560;
        }}

        .catalog-item {{
            padding: 0.3rem 0;
            border-bottom: 1px solid #0f3460;
            font-size: 0.8rem;
            display: flex;
            align-items: baseline;
            gap: 0.3rem;
            cursor: pointer;
        }}
        .catalog-item:hover {{
            background: #0f3460;
        }}
        .catalog-item:last-child {{
            border-bottom: none;
        }}
        .catalog-size {{
            color: #e94560;
            flex-shrink: 0;
        }}
        .catalog-path {{
            font-family: monospace;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .path-bar {{
            background: #16213e;
            padding: 0.75rem 2rem;
            border-bottom: 1px solid #0f3460;
            font-family: monospace;
            font-size: 0.9rem;
            word-break: break-all;
        }}
        .path-bar .label {{
            color: #888;
            margin-right: 0.5rem;
        }}
        .path-bar .path {{
            color: #e94560;
        }}
    </style>
</head>
<body>
    <header>
        <h1><a href="https://chrisburr.github.io/cvmfs-catalog-visualizations/" style="color: inherit; text-decoration: none;">CVMFS Catalog Visualizer</a> - <span class="repo-name">{repo_name}</span></h1>
    </header>

    <div class="path-bar">
        <span class="label">Selected:</span>
        <span class="path" id="info-path">/</span>
    </div>

    <div class="container">
        <div class="chart-container">
            <canvas id="chart"></canvas>
            <div class="legend">
                <div class="legend-title">Size Legend</div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #22c55e;"></div>
                    <span>&lt; 2 MB</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #eab308;"></div>
                    <span>2 - 10 MB</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #f97316;"></div>
                    <span>10 - 50 MB</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ef4444;"></div>
                    <span>&gt; 50 MB</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #c15b5b;"></div>
                    <span>Stopped</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #4a5568;"></div>
                    <span>Virtual</span>
                </div>
            </div>
        </div>

        <div class="sidebar">
            <h2>Selected Catalog</h2>
            <div class="info-panel" id="info-panel">
                <div class="info-row">
                    <span class="info-label">Catalog Size</span>
                    <span class="info-value" id="info-size">-</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Cumulative Cost</span>
                    <span class="info-value" id="info-cost">-</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Depth</span>
                    <span class="info-value" id="info-depth">-</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Hash</span>
                    <span class="info-value hash" id="info-hash" title="Click to copy">-</span>
                </div>
                <div id="large-badge"></div>
            </div>

            <h2>Largest Catalogs</h2>
            <div class="info-panel" id="largest-catalogs">
                <!-- Populated by JavaScript -->
            </div>

            <div class="instructions">
                <strong>Instructions:</strong><br>
                • Click on a segment to zoom in<br>
                • Click center to zoom out<br>
                • Hover for details
            </div>

            <div class="tips">
                <strong>Why are catalogs large?</strong><br>
                Catalog size = metadata entries, not file sizes.
                A catalog with many files/directories has a large database.<br><br>
                <strong>Investigate further:</strong>
                <div class="command-box" id="explore-command">
                    catalog_explorer {repo_name} du /
                </div>
            </div>

            <div class="stats">
                Generated: {generated_at}
            </div>
        </div>
    </div>

    <script>
    const data = {data_json};

    // Enrich tree: recompute depth and cumulative_cost (dropped from JSON for size)
    function enrichTree(node, depth, parentCost) {{
        node.depth = depth;
        node.cumulative_cost = parentCost + (node.size || 0);
        if (node.children) {{
            for (const c of node.children) enrichTree(c, depth + 1, node.cumulative_cost);
        }}
    }}
    enrichTree(data, 0, 0);

    const width = 800;
    const height = 800;
    const radius = width / 12;

    // Desaturate a hex color by blending with gray
    function desaturate(hex, amount) {{
        if (amount === undefined) amount = 0.4;
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        const gray = (r + g + b) / 3;
        const nr = Math.round(r + (gray - r) * amount);
        const ng = Math.round(g + (gray - g) * amount);
        const nb = Math.round(b + (gray - b) * amount);
        return '#' + nr.toString(16).padStart(2, '0') + ng.toString(16).padStart(2, '0') + nb.toString(16).padStart(2, '0');
    }}

    // Color scale based on size
    function sizeColor(size) {{
        const mb = size / (1024 * 1024);
        if (mb < 2) return "#22c55e";
        if (mb < 10) return "#eab308";
        if (mb < 50) return "#f97316";
        return "#ef4444";
    }}

    function getColor(d) {{
        if (d.data.is_virtual) return "#4a5568";
        let color = sizeColor(d.data.size || 0);
        if (d.data.is_large && !d.children) {{
            color = desaturate(color);
        }}
        return color;
    }}

    // Format bytes
    function formatBytes(bytes) {{
        if (bytes === 0) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    }}

    // Create hierarchy - siblings share parent's arc equally
    const root = d3.hierarchy(data);
    root.value = 1;
    root.eachBefore(d => {{
        if (d.children) {{
            const childValue = d.value / d.children.length;
            d.children.forEach(c => c.value = childValue);
        }}
    }});

    const partition = d3.partition()
        .size([2 * Math.PI, root.height + 1]);

    partition(root);

    root.each(d => {{
        d.current = {{ x0: d.x0, x1: d.x1, y0: d.y0, y1: d.y1 }};
    }});

    // Canvas setup with HiDPI support
    const canvas = document.getElementById('chart');
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    // Precompute flat list of descendants (excluding root) for drawing/hit testing
    const descendants = root.descendants().slice(1);

    // Track state
    let currentNode = root;
    let hoveredNode = null;
    let animating = false;

    function arcVisible(d) {{
        return d.y1 <= 6 && d.y0 >= 1 && d.x1 > d.x0;
    }}

    function drawArc(cx, cy, x0, x1, innerR, outerR, color, opacity) {{
        if (x1 - x0 < 0.001) return;
        const startAngle = x0 - Math.PI / 2;
        const endAngle = x1 - Math.PI / 2;
        ctx.beginPath();
        ctx.arc(cx, cy, outerR, startAngle, endAngle);
        ctx.arc(cx, cy, innerR, endAngle, startAngle, true);
        ctx.closePath();
        ctx.globalAlpha = opacity;
        ctx.fillStyle = color;
        ctx.fill();
    }}

    function draw() {{
        const cx = width / 2;
        const cy = height / 2;

        ctx.clearRect(0, 0, width, height);

        // Draw arcs
        for (const d of descendants) {{
            if (!arcVisible(d.current)) continue;
            const innerR = d.current.y0 * radius;
            const outerR = Math.max(d.current.y0 * radius, d.current.y1 * radius - 1);
            const color = getColor(d);
            let opacity;
            if (d === hoveredNode) {{
                opacity = 1;
            }} else {{
                opacity = d.children ? 0.8 : 0.6;
            }}
            drawArc(cx, cy, d.current.x0, d.current.x1, innerR, outerR, color, opacity);
        }}

        // Draw center circle
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, 2 * Math.PI);
        ctx.closePath();
        ctx.globalAlpha = hoveredNode === currentNode ? 1 : 0.9;
        ctx.fillStyle = getColor(currentNode);
        ctx.fill();

        // Draw center text
        ctx.globalAlpha = 1;
        ctx.fillStyle = '#eee';
        ctx.font = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Click to zoom out', cx, cy);
    }}

    function hitTest(clientX, clientY) {{
        const rect = canvas.getBoundingClientRect();
        const mx = (clientX - rect.left) * (width / rect.width) - width / 2;
        const my = (clientY - rect.top) * (height / rect.height) - height / 2;
        const r = Math.sqrt(mx * mx + my * my);

        // Check center circle
        if (r < radius) return currentNode;

        let angle = Math.atan2(my, mx) + Math.PI / 2;
        if (angle < 0) angle += 2 * Math.PI;

        for (const d of descendants) {{
            if (!arcVisible(d.current)) continue;
            const innerR = d.current.y0 * radius;
            const outerR = Math.max(d.current.y0 * radius, d.current.y1 * radius - 1);
            if (r >= innerR && r <= outerR && angle >= d.current.x0 && angle < d.current.x1) {{
                return d;
            }}
        }}
        return null;
    }}

    // Update info panel
    function updateInfo(d) {{
        document.getElementById("info-path").textContent = d.data.path || "/";
        document.getElementById("info-size").textContent = formatBytes(d.data.size || 0);
        document.getElementById("info-cost").textContent = formatBytes(d.data.cumulative_cost || 0);
        document.getElementById("info-depth").textContent = d.data.depth || 0;
        document.getElementById("info-hash").textContent = d.data.hash || "-";

        const badge = document.getElementById("large-badge");
        if (d.data.is_virtual) {{
            badge.innerHTML = '<span class="large-indicator" style="background: #4a5568;">Directory (no catalog)</span>';
        }} else if (d.data.is_large) {{
            badge.innerHTML = '<span class="large-indicator">Large catalog - exploration stopped</span>';
        }} else {{
            badge.innerHTML = "";
        }}
    }}

    canvas.addEventListener('mousemove', function(event) {{
        if (animating) return;
        const hit = hitTest(event.clientX, event.clientY);
        if (hit !== hoveredNode) {{
            hoveredNode = hit;
            canvas.style.cursor = hit ? 'pointer' : 'default';
            if (hit) {{
                updateInfo(hit);
            }} else {{
                updateInfo(currentNode);
            }}
            draw();
        }}
    }});

    canvas.addEventListener('mouseleave', function() {{
        if (hoveredNode) {{
            hoveredNode = null;
            canvas.style.cursor = 'default';
            updateInfo(currentNode);
            draw();
        }}
    }});

    canvas.addEventListener('click', function(event) {{
        if (animating) return;
        const hit = hitTest(event.clientX, event.clientY);
        if (!hit) return;

        if (hit === currentNode) {{
            // Clicking center: zoom out to parent
            if (currentNode.parent) {{
                clicked(currentNode.parent);
            }}
        }} else {{
            clicked(hit);
        }}
    }});

    function clicked(p) {{
        root.each(d => {{
            d.target = {{
                x0: Math.max(0, Math.min(1, (d.x0 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI,
                x1: Math.max(0, Math.min(1, (d.x1 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI,
                y0: Math.max(0, d.y0 - p.depth),
                y1: Math.max(0, d.y1 - p.depth)
            }};
        }});

        // Save start positions for interpolation
        root.each(d => {{
            d._start = {{ x0: d.current.x0, x1: d.current.x1, y0: d.current.y0, y1: d.current.y1 }};
        }});

        currentNode = p;
        hoveredNode = null;
        updateInfo(p);
        updateLargestCatalogs(p);
        updateExploreCommand(p);

        const duration = 750;
        const start = performance.now();
        animating = true;

        function animate(now) {{
            const elapsed = now - start;
            const t = Math.min(1, elapsed / duration);
            // Ease-in-out quadratic
            const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;

            root.each(d => {{
                d.current.x0 = d._start.x0 + (d.target.x0 - d._start.x0) * ease;
                d.current.x1 = d._start.x1 + (d.target.x1 - d._start.x1) * ease;
                d.current.y0 = d._start.y0 + (d.target.y0 - d._start.y0) * ease;
                d.current.y1 = d._start.y1 + (d.target.y1 - d._start.y1) * ease;
            }});

            draw();

            if (t < 1) {{
                requestAnimationFrame(animate);
            }} else {{
                animating = false;
            }}
        }}

        requestAnimationFrame(animate);
    }}

    // Update largest catalogs list for a given hierarchy node
    function updateLargestCatalogs(hierarchyNode) {{
        const catalogs = hierarchyNode.descendants()
            .filter(d => !d.data.is_virtual && d.data.size > 0)
            .map(d => ({{ path: d.data.path, size: d.data.size }}))
            .sort((a, b) => b.size - a.size)
            .slice(0, 10);

        const listHtml = catalogs.map(c =>
            '<div class="catalog-item" data-path="' + c.path + '" title="' + c.path + '">' +
                '<span class="catalog-size" style="color: ' + sizeColor(c.size) + '">' + formatBytes(c.size) + ':</span>' +
                '<span class="catalog-path">' + c.path + '</span>' +
            '</div>'
        ).join('');
        document.getElementById('largest-catalogs').innerHTML = listHtml;

        // Click to zoom in chart
        document.querySelectorAll('.catalog-item').forEach(item => {{
            item.addEventListener('click', () => {{
                const targetPath = item.dataset.path;
                const targetNode = root.descendants().find(d => d.data.path === targetPath);
                if (targetNode) {{
                    clicked(targetNode);
                }}
            }});
        }});
    }}

    // Initial info and sidebar population
    updateInfo(root);
    updateLargestCatalogs(root);

    // Update explore command for current path
    const repoUrl = "{repo_url}";
    function updateExploreCommand(node) {{
        const path = node.data.path || "/";
        const cmd = 'catalog_explorer ' + repoUrl + ' du ' + path;
        document.getElementById('explore-command').textContent = cmd;
    }}
    updateExploreCommand(root);

    // Click to copy hash
    document.getElementById('info-hash').addEventListener('click', function() {{
        const hash = this.textContent;
        if (hash && hash !== '-') {{
            navigator.clipboard.writeText(hash).then(() => {{
                const original = this.textContent;
                this.textContent = 'Copied!';
                setTimeout(() => this.textContent = original, 1000);
            }});
        }}
    }});

    // Click to copy explore command
    document.getElementById('explore-command').addEventListener('click', function() {{
        const cmd = this.textContent;
        navigator.clipboard.writeText(cmd).then(() => {{
            const original = this.textContent;
            this.textContent = 'Copied!';
            setTimeout(() => this.textContent = original, 1000);
        }});
    }});

    // Initial draw
    draw();
    </script>
</body>
</html>
"""


def generate_html(
    root_node: CatalogNode,
    repo_name: str,
    repo_url: str = "",
    generated_at: str = "",
) -> str:
    """Generate a self-contained HTML visualization.

    Args:
        root_node: Root CatalogNode from tree builder
        repo_name: Repository name for display
        repo_url: Full repository URL for commands
        generated_at: Timestamp string for when the visualization was generated

    Returns:
        Complete HTML string
    """
    data_dict = root_node.to_dict()
    data_json = json.dumps(data_dict, separators=(",", ":"))

    return HTML_TEMPLATE.format(
        repo_name=repo_name,
        repo_url=repo_url or repo_name,
        d3_cdn=D3_CDN,
        data_json=data_json,
        generated_at=generated_at,
    )
