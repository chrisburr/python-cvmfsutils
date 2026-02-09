# -*- coding: utf-8 -*-
"""
HTML generator for CVMFS catalog visualization.

Generates a self-contained HTML file with an interactive D3.js sunburst chart.
"""

import json
from typing import Union

from .tree_builder import CatalogNode

# D3.js CDN URL
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
            width: 100%;
            height: auto;
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

        .breadcrumb {{
            font-family: monospace;
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 1rem;
            word-break: break-all;
        }}

        .breadcrumb span {{
            color: #e94560;
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

        svg text {{
            pointer-events: none;
            user-select: none;
        }}

        .path-bar {{
            background: #16213e;
            padding: 0.75rem 2rem;
            border-top: 1px solid #0f3460;
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
        <h1>CVMFS Catalog Visualizer - <span class="repo-name">{repo_name}</span></h1>
    </header>

    <div class="container">
        <div class="chart-container">
            <svg id="chart"></svg>
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
            <div class="breadcrumb">
                Current view: <span id="breadcrumb">/</span>
            </div>

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

    <div class="path-bar">
        <span class="label">Selected:</span>
        <span class="path" id="info-path">/</span>
    </div>

    <script>
    const data = {data_json};

    const width = 800;
    const height = 800;
    const radius = width / 12;

    // Desaturate a hex color by blending with gray
    function desaturate(hex, amount = 0.4) {{
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        const gray = (r + g + b) / 3;
        const nr = Math.round(r + (gray - r) * amount);
        const ng = Math.round(g + (gray - g) * amount);
        const nb = Math.round(b + (gray - b) * amount);
        return `#${{nr.toString(16).padStart(2, '0')}}${{ng.toString(16).padStart(2, '0')}}${{nb.toString(16).padStart(2, '0')}}`;
    }}

    // Color scale based on size
    function getColor(d) {{
        // Virtual nodes (path intermediates without catalogs) are gray
        if (d.data.is_virtual) return "#4a5568";

        const size = d.data.size || 0;
        const mb = size / (1024 * 1024);

        let color;
        if (mb < 2) color = "#22c55e";      // Green - small
        else if (mb < 10) color = "#eab308"; // Yellow - medium
        else if (mb < 50) color = "#f97316"; // Orange - large
        else color = "#ef4444";              // Red - very large

        // Desaturate if exploration was stopped
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

    root.each(d => d.current = d);

    // Create SVG
    const svg = d3.select("#chart")
        .attr("viewBox", [-width / 2, -height / 2, width, height])
        .style("font", "10px sans-serif");

    // Arc generator
    const arc = d3.arc()
        .startAngle(d => d.x0)
        .endAngle(d => d.x1)
        .padAngle(d => Math.min((d.x1 - d.x0) / 2, 0.005))
        .padRadius(radius * 1.5)
        .innerRadius(d => d.y0 * radius)
        .outerRadius(d => Math.max(d.y0 * radius, d.y1 * radius - 1));

    // Create paths
    const path = svg.append("g")
        .selectAll("path")
        .data(root.descendants().slice(1))
        .join("path")
        .attr("fill", d => getColor(d))
        .attr("fill-opacity", d => arcVisible(d.current) ? (d.children ? 0.8 : 0.6) : 0)
        .attr("pointer-events", d => arcVisible(d.current) ? "auto" : "none")
        .attr("d", d => arc(d.current))
        .style("cursor", "pointer")
        .on("mouseover", handleMouseOver)
        .on("mouseout", handleMouseOut)
        .on("click", clicked);

    // Center circle for zooming out to root
    const parent = svg.append("circle")
        .datum(root)
        .attr("r", radius)
        .attr("fill", "#16213e")
        .attr("pointer-events", "all")
        .style("cursor", "pointer")
        .on("click", () => clicked(null, root))
        .on("mouseover", handleMouseOver)
        .on("mouseout", handleMouseOut);

    // Center text
    const centerText = svg.append("text")
        .attr("text-anchor", "middle")
        .attr("fill", "#eee")
        .attr("dy", "0.35em")
        .style("font-size", "14px")
        .text("Click to zoom out");

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

    // Track current zoomed node for restoring info on mouseout
    let currentNode = root;

    function handleMouseOver(event, d) {{
        updateInfo(d);
        d3.select(this).attr("fill-opacity", 1);
    }}

    function handleMouseOut(event, d) {{
        d3.select(this).attr("fill-opacity", d => arcVisible(d.current) ? (d.children ? 0.8 : 0.6) : 0);
        updateInfo(currentNode);
    }}

    // Initial info
    updateInfo(root);

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

    function clicked(event, p) {{
        parent.datum(p.parent || root);

        root.each(d => d.target = {{
            x0: Math.max(0, Math.min(1, (d.x0 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI,
            x1: Math.max(0, Math.min(1, (d.x1 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI,
            y0: Math.max(0, d.y0 - p.depth),
            y1: Math.max(0, d.y1 - p.depth)
        }});

        const t = svg.transition().duration(750);

        path.transition(t)
            .tween("data", d => {{
                const i = d3.interpolate(d.current, d.target);
                return t => d.current = i(t);
            }})
            .filter(function(d) {{
                return +this.getAttribute("fill-opacity") || arcVisible(d.target);
            }})
            .attr("fill-opacity", d => arcVisible(d.target) ? (d.children ? 0.8 : 0.6) : 0)
            .attr("pointer-events", d => arcVisible(d.target) ? "auto" : "none")
            .attrTween("d", d => () => arc(d.current));

        // Update breadcrumb and current node
        currentNode = p;
        let breadcrumb = p.data.path || "/";
        document.getElementById("breadcrumb").textContent = breadcrumb;

        updateInfo(p);
        updateLargestCatalogs(p);
        updateExploreCommand(p);
    }}

    function arcVisible(d) {{
        return d.y1 <= 6 && d.y0 >= 1 && d.x1 > d.x0;
    }}

    // Update largest catalogs list for a given hierarchy node
    function updateLargestCatalogs(hierarchyNode) {{
        const catalogs = hierarchyNode.descendants()
            .filter(d => !d.data.is_virtual && d.data.size > 0)
            .map(d => ({{ path: d.data.path, size: d.data.size }}))
            .sort((a, b) => b.size - a.size)
            .slice(0, 10);

        const listHtml = catalogs.map(c =>
            `<div class="catalog-item" data-path="${{c.path}}" title="${{c.path}}">
                <span class="catalog-size">${{formatBytes(c.size)}}:</span>
                <span class="catalog-path">${{c.path}}</span>
            </div>`
        ).join('');
        document.getElementById('largest-catalogs').innerHTML = listHtml;

        // Click to zoom in chart
        document.querySelectorAll('.catalog-item').forEach(item => {{
            item.addEventListener('click', () => {{
                const targetPath = item.dataset.path;
                const targetNode = root.descendants().find(d => d.data.path === targetPath);
                if (targetNode) {{
                    clicked(null, targetNode);
                }}
            }});
        }});
    }}

    // Initial population
    updateLargestCatalogs(root);

    // Update explore command for current path
    const repoUrl = "{repo_url}";
    function updateExploreCommand(node) {{
        const path = node.data.path || "/";
        const cmd = `catalog_explorer ${{repoUrl}} du ${{path}}`;
        document.getElementById('explore-command').textContent = cmd;
    }}
    updateExploreCommand(root);

    // Click to copy explore command
    document.getElementById('explore-command').addEventListener('click', function() {{
        const cmd = this.textContent;
        navigator.clipboard.writeText(cmd).then(() => {{
            const original = this.textContent;
            this.textContent = 'Copied!';
            setTimeout(() => this.textContent = original, 1000);
        }});
    }});
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
    data_json = json.dumps(data_dict, indent=2)

    return HTML_TEMPLATE.format(
        repo_name=repo_name,
        repo_url=repo_url or repo_name,
        d3_cdn=D3_CDN,
        data_json=data_json,
        generated_at=generated_at,
    )
