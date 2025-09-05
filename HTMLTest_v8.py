import requests
import time
import os
from datetime import datetime
from collections import Counter

# --- Configuration ---
# The API Key will be read from a secure environment variable.
API_KEY = os.getenv('CR_API_KEY')

# 2. List of all clans in the family, in the desired report order.
DARK_FAMILY_CLANS = [
    ("Dark Humor", "#2V2VRRLJ"),
    ("Dark Vendetta", "#8UCRLJ0J"),
    ("Dark Inception", "#8Y8UG0JJ"),
    ("Dark Intentions", "#YUYP9229"),
    ("Dark Disciples", "#L2VCQ0V8"),
    ("Dark Prestige", "#QPY80LRQ"),
    ("Dusted Compass", "#Q80YJGGG"),
    ("Dark Paradox", "#9C8Y0QGY")
]

# List of top clan tags to apply the 'fair benchmark' logic to.
# Other clans will default to a 16-battle benchmark.
TOP_CLANS_FOR_BENCHMARK = {"#2V2VRRLJ", "#8UCRLJ0J", "#8Y8UG0JJ", "#YUYP9229"}
# --- End of Configuration ---

BASE_URL = "https://api.clashroyale.com/v1"

def get_api_data(endpoint, clan_tag):
    """Fetches data for a specific clan from a specific API endpoint."""
    encoded_clan_tag = clan_tag.replace("#", "%23")
    url = f"{BASE_URL}{endpoint.replace('{clanTag}', encoded_clan_tag)}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error for clan {clan_tag}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code == 403: print("-> Forbidden: Check API key and whitelisted IP address.")
            elif e.response.status_code == 404: print(f"-> Not Found: Check if Clan Tag '{clan_tag}' is correct.")
            elif e.response.status_code == 503: print("-> Service Unavailable: Clash Royale API might be down.")
        return None

def calculate_fair_benchmark(participants):
    """
    Calculates a fair benchmark for total possible attacks in a war,
    accounting for early finishes by finding the most common participation level.
    """
    if not participants:
        return 16

    decks_used_list = [p.get('decksUsed', 0) for p in participants if p.get('decksUsed', 0) > 0]
    if not decks_used_list:
        return 16

    max_attacks = max(decks_used_list)
    
    deck_counts = Counter(decks_used_list)
    most_common_attacks = deck_counts.most_common(1)[0][0]

    if most_common_attacks in [4, 8, 12] and most_common_attacks < max_attacks:
        return most_common_attacks
    
    return max_attacks

def generate_html_for_clan(clan_name, clan_tag, is_first_clan):
    """Fetches data and generates an HTML string for a single clan's report section."""
    print(f"Fetching data for {clan_name} ({clan_tag})...")
    clan_data = get_api_data("/clans/{clanTag}", clan_tag)
    current_war_data = get_api_data("/clans/{clanTag}/currentriverrace", clan_tag)
    war_log_data = get_api_data("/clans/{clanTag}/riverracelog?limit=5", clan_tag)

    clan_id = clan_tag.replace('#', '')
    
    if not all([clan_data, current_war_data, war_log_data]):
        return f"""<div id="{clan_id}" class="clan-section {'active' if is_first_clan else ''}">
                     <div class="p-8 bg-gray-800 rounded-lg shadow-lg">
                        <h2 class="text-3xl font-bold text-purple-400 mb-2">{clan_name.upper()}</h2>
                        <p class="text-gray-400">{clan_tag}</p>
                        <p class="mt-4 text-red-400">Could not generate report due to an API error.</p>
                     </div>
                   </div>"""

    current_member_tags = {member['tag'] for member in clan_data.get('memberList', [])}
    player_stats = {
        member['tag']: {
            'name': member['name'], 'current_war_decks_used': 0, 'current_war_fame': 0,
            'total_war_fame': 0, 'total_decks_used': 0, 'war_history': {}
        } for member in clan_data.get('memberList', [])
    }

    for p in current_war_data.get('clan', {}).get('participants', []):
        if p.get('tag') in player_stats:
            player_stats[p['tag']]['current_war_decks_used'] = p.get('decksUsed', 0)
            player_stats[p['tag']]['current_war_fame'] = p.get('fame', 0)

    war_log_items = war_log_data.get('items', [])
    war_ids = [f"War {i+1} ({war.get('createdDate', 'N/A').split('T')[0]})" for i, war in enumerate(war_log_items)]

    all_participants = set(player_stats.keys())
    for war in war_log_items:
        for standing in war.get('standings', []):
            if standing.get('clan', {}).get('tag') == clan_tag:
                for p in standing.get('clan', {}).get('participants', []):
                    all_participants.add(p.get('tag'))

    for tag in all_participants:
        if tag not in player_stats:
            player_stats[tag] = {'name': "Former Member (*)", 'current_war_decks_used': 0, 'current_war_fame': 0,
                                 'total_war_fame': 0, 'total_decks_used': 0, 'war_history': {}}

    war_benchmarks = {}
    for i, war in enumerate(war_log_items):
        war_id = war_ids[i]
        
        war_participants = []
        for standing in war.get('standings', []):
            if standing.get('clan', {}).get('tag') == clan_tag:
                war_participants = standing.get('clan', {}).get('participants', [])
                break
        
        benchmark = 16
        if clan_tag in TOP_CLANS_FOR_BENCHMARK:
            benchmark = calculate_fair_benchmark(war_participants)
        
        war_benchmarks[war_id] = benchmark

        for tag in player_stats:
            player_stats[tag]['war_history'][war_id] = {'fame': 0, 'decksUsed': 0}
        
        for p in war_participants:
            tag, fame, decks_used = p.get('tag'), p.get('fame', 0), p.get('decksUsed', 0)
            if tag in player_stats:
                if player_stats[tag]['name'] == "Former Member (*)":
                     player_stats[tag]['name'] = f"{p.get('name')} (*)"
                player_stats[tag]['war_history'][war_id] = {'fame': fame, 'decksUsed': decks_used}
                player_stats[tag]['total_war_fame'] += fame
                player_stats[tag]['total_decks_used'] += decks_used
    
    html = f"""
    <div id="{clan_id}" class="clan-section {'active' if is_first_clan else ''}" data-clan-id="{clan_id}">
        <div class="p-4 md:p-8">
            <div class="flex items-center justify-between mb-6">
                <div>
                    <h2 class="text-3xl font-bold text-purple-400">{clan_name.upper()}</h2>
                    <p class="text-gray-400 font-mono text-sm">{clan_tag}</p>
                </div>
                <div class="text-sm text-gray-400">
                    <img src="{clan_data.get('badgeUrls', {}).get('large', '')}" alt="{clan_name} Badge" class="w-20 h-20 md:w-24 md:h-24 inline-block">
                </div>
            </div>
            <div class="mb-6">
                <div class="border-b border-gray-700">
                    <nav class="-mb-px flex space-x-2 sm:space-x-4 md:space-x-8 overflow-x-auto" aria-label="Tabs">
                        <button class="tab-btn active whitespace-nowrap" data-tab-target="current-war-{clan_id}">Current War</button>
                        <button class="tab-btn whitespace-nowrap" data-tab-target="war-log-{clan_id}">War Log</button>
                        <button class="tab-btn whitespace-nowrap" data-tab-target="performance-{clan_id}">Performance</button>
                        <button class="tab-btn whitespace-nowrap" data-tab-target="history-{clan_id}">History</button>
                    </nav>
                </div>
            </div>
            <div id="current-war-{clan_id}" class="tab-content active">{build_current_war_html(current_war_data, player_stats, current_member_tags)}</div>
            <div id="war-log-{clan_id}" class="tab-content">{build_war_log_html(war_log_items, clan_tag)}</div>
            <div id="performance-{clan_id}" class="tab-content">{build_performance_html(player_stats, current_member_tags, war_ids, war_benchmarks)}</div>
            <div id="history-{clan_id}" class="tab-content">{build_history_html(player_stats, current_member_tags, war_ids, war_benchmarks)}</div>
        </div>
    </div>
    """
    return html

def build_current_war_html(current_war_data, player_stats, current_member_tags):
    war_state = current_war_data.get('state', 'N/A')
    html = '<div class="bg-gray-800 p-4 sm:p-6 rounded-lg">'
    if war_state in ['inWar', 'full', 'warDay']:
        period_index = current_war_data.get('periodIndex', 0)
        war_day_number = max(1, period_index - 2)
        cumulative_max_battles = war_day_number * 4
        html += f'<h3 class="text-xl font-bold text-purple-400 mb-4">Current River Race - Day {war_day_number}</h3>'
        html += f'<p class="text-sm text-gray-400 mb-4"><b>API State:</b> {war_state}</p>'
        all_current_members_data = sorted([s for tag, s in player_stats.items() if tag in current_member_tags], key=lambda x: (-x['current_war_fame'], -x['current_war_decks_used'], x['name'].lower()))
        html += '<div class="overflow-x-auto"><table class="w-full"><thead><tr class="text-left text-xs text-gray-400 uppercase tracking-wider"><th>Player</th><th class="text-center">Attacks</th><th class="text-right">Fame</th></tr></thead><tbody class="divide-y divide-gray-700">'
        for s in all_current_members_data:
            decks_used = s.get('current_war_decks_used', 0)
            daily_status_html = f' <span class="block text-green-400 text-xs italic">(All Battles Complete!)</span>' if decks_used >= cumulative_max_battles else f' <span class="block text-yellow-500 text-xs italic">(Waiting on Day {war_day_number} Battles)</span>'
            missed_battle_indicator_html = ' <span class="block text-red-500 text-xs italic">(Missed Battle(s) on Prior Day)</span>' if war_day_number > 1 and decks_used < (war_day_number - 1) * 4 else ''
            indicators_html = f"{daily_status_html}{missed_battle_indicator_html}"
            html += f'<tr><td class="py-3 pr-3"><div>{s["name"]}{indicators_html}</div></td><td class="py-3 px-3 text-center align-top">{decks_used} / {cumulative_max_battles}</td><td class="py-3 pl-3 text-right font-semibold align-top">{s["current_war_fame"]}</td></tr>'
        html += '</tbody></table></div>'
    else:
        state_descriptions = {'warEnded': 'The previous war has just completed.', 'training': 'This is a training week.', 'matchmaking': 'Matchmaking for the next war.'}
        description = state_descriptions.get(war_state, 'Unknown state.')
        html += f'<h3 class="text-xl font-bold text-purple-400 mb-4">No Active War</h3>'
        html += f'<p class="text-gray-300">{description} (API State: {war_state})</p>'
        html += "<p class='text-xs text-gray-500 mt-2'>New war information will be available via the API shortly after it begins.</p>"
    html += '</div>'
    return html

def build_war_log_html(war_log_items, clan_tag):
    html = '<div class="bg-gray-800 p-4 sm:p-6 rounded-lg">'
    html += '<h3 class="text-xl font-bold text-purple-400 mb-4">River Race Log (Last 5 Wars)</h3>'
    html += '<div class="overflow-x-auto"><table class="w-full"><thead><tr class="text-left text-xs text-gray-400 uppercase tracking-wider"><th>Date</th><th class="text-center">Rank</th><th class="text-right">Trophy Change</th></tr></thead><tbody class="divide-y divide-gray-700">'
    for war in war_log_items:
        for standing in war.get('standings', []):
            if standing.get('clan', {}).get('tag') == clan_tag:
                trophy_change = standing.get('trophyChange', 0)
                trophy_class = 'text-gray-400'
                if trophy_change > 0: trophy_class = 'text-green-400'
                elif trophy_change < 0: trophy_class = 'text-red-400'
                html += f'<tr><td class="py-3 pr-3">{war.get("createdDate", "N/A").split("T")[0]}</td><td class="py-3 px-3 text-center">{standing.get("rank", "N/A")}</td><td class="py-3 pl-3 text-right font-semibold {trophy_class}">{trophy_change}</td></tr>'
                break
    html += '</tbody></table></div></div>'
    return html

def build_performance_html(player_stats, current_member_tags, war_ids, war_benchmarks):
    html = '<div class="bg-gray-800 p-4 sm:p-6 rounded-lg">'
    html += '<h3 class="text-xl font-bold text-purple-400 mb-4">War Performance Averages (Last 5 Wars)</h3>'
    html += '<div class="overflow-x-auto"><table class="w-full"><thead><tr class="text-left text-xs text-gray-400 uppercase tracking-wider"><th>Player</th><th class="text-center">Total Battles</th><th class="text-right">Total Fame</th><th class="text-right">Avg Fame/Battle</th></tr></thead><tbody class="divide-y divide-gray-700">'
    current_members_perf = sorted([p for tag, p in player_stats.items() if tag in current_member_tags], key=lambda x: -x['total_war_fame'])
    total_possible_battles = sum(war_benchmarks.values())
    for s in current_members_perf:
        avg_fame = s['total_war_fame'] / s['total_decks_used'] if s['total_decks_used'] > 0 else 0
        missed_battles_html = f' <span class="block text-red-500 text-xs italic">(Missed Battles)</span>' if s['total_decks_used'] < total_possible_battles else ''
        html += f'<tr><td class="py-3 pr-3"><div>{s["name"]}{missed_battles_html}</div></td><td class="py-3 px-3 text-center align-top">{s["total_decks_used"]} / {total_possible_battles}</td><td class="py-3 px-3 text-right font-semibold align-top">{s["total_war_fame"]}</td><td class="py-3 pl-3 text-right font-semibold align-top">{avg_fame:.2f}</td></tr>'
    html += '</tbody></table></div></div>'
    return html

def build_history_html(player_stats, current_member_tags, war_ids, war_benchmarks):
    html = '<div class="space-y-4">'
    html += '<h3 class="text-xl font-bold text-purple-400 mb-4">Last 5 Wars - Player History</h3>'
    for war_id in war_ids:
        war_date = war_id.split('(')[-1][:-1]
        benchmark = war_benchmarks.get(war_id, 16)
        html += f'<details class="bg-gray-800 rounded-lg"><summary class="p-4 cursor-pointer font-semibold text-purple-300">War Date: {war_date}</summary><div class="p-4 border-t border-gray-700">'
        html += '<table class="w-full"><thead><tr class="text-left text-xs text-gray-400 uppercase tracking-wider"><th>Player</th><th class="text-center">Battles</th><th class="text-right">Score</th></tr></thead><tbody class="divide-y divide-gray-700">'
        current_p, former_p = [], []
        for tag, player in player_stats.items():
            history = player['war_history'].get(war_id, {'decksUsed': 0, 'fame': 0})
            if history['decksUsed'] > 0 or history['fame'] > 0:
                p_data = (player['name'], history['decksUsed'], history['fame'])
                if tag not in current_member_tags: former_p.append(p_data)
                else: current_p.append(p_data)
        current_p.sort(key=lambda x: -x[2]); former_p.sort(key=lambda x: -x[2])
        for name, decks, fame in current_p:
            missed_battles_html = f' <span class="block text-red-500 text-xs italic">(Missed Battles)</span>' if decks < benchmark else ''
            html += f'<tr><td class="py-2 pr-2"><div>{name}{missed_battles_html}</div></td><td class="py-2 px-2 text-center align-top">{decks}/{benchmark}</td><td class="py-2 pl-2 text-right font-semibold align-top">{fame}</td></tr>'
        if former_p:
            html += '<tr><td colspan="3" class="pt-4 pb-2 text-center text-sm font-bold text-gray-500 uppercase">--- Former Members ---</td></tr>'
            for name, decks, fame in former_p:
                 missed_battles_html = f' <span class="block text-red-500 text-xs italic">(Missed Battles)</span>' if decks < benchmark else ''
                 html += f'<tr><td class="py-2 pr-2"><div>{name}{missed_battles_html}</div></td><td class="py-2 px-2 text-center align-top">{decks}/{benchmark}</td><td class="py-2 pl-2 text-right font-semibold align-top">{fame}</td></tr>'
        html += '</tbody></table></div></details>'
    html += '</div>'
    return html

def generate_master_html_report():
    now = datetime.now()
    clan_sections_html = ""
    nav_links = ""

    for i, (clan_name, clan_tag) in enumerate(DARK_FAMILY_CLANS):
        is_first = (i == 0)
        clan_id = clan_tag.replace('#', '')
        nav_links += f'<li><a href="#{clan_id}" class="nav-link {"active" if is_first else ""}" data-clan-target="{clan_id}">{clan_name}</a></li>'
        clan_sections_html += generate_html_for_clan(clan_name, clan_tag, is_first)
        time.sleep(1)

    html_template = f"""
    <!DOCTYPE html>
    <html lang="en" class="dark">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dark Family War Report</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{ font-family: 'Inter', sans-serif; background-color: #111827; }}
            .clan-section {{ display: none; }}
            .clan-section.active {{ display: block; }}
            .tab-content {{ display: none; }}
            .tab-content.active {{ display: block; }}
            .nav-link {{ 
                color: #a78bfa; 
                font-weight: 600;
            }}
            .nav-link.active {{ 
                background-color: #4c1d95; 
                color: white; 
            }}
            .tab-btn {{
                padding: 0.5rem 1rem;
                border-bottom: 2px solid transparent;
                transition: all 0.3s ease;
                color: #9ca3af;
            }}
            .tab-btn.active {{ color: #a78bfa; border-color: #a78bfa; }}
            .sidebar {{ -ms-overflow-style: none; scrollbar-width: none; }}
            .sidebar::-webkit-scrollbar {{ display: none; }}
        </style>
    </head>
    <body class="text-gray-300">
        <div class="relative min-h-screen md:flex">
            <div class="md:hidden flex justify-between items-center bg-gray-800 p-4">
                <div><h1 class="text-lg font-bold text-purple-400">Dark Family</h1></div>
                <div class="flex items-center space-x-4">
                     <div class="text-right text-[10px] text-gray-400">
                        <p>{now.strftime('%Y-%m-%d %I:%M %p')}</p>
                        <img src="https://hitscounter.dev/api/hit?url=https%3A%2F%2Fthelucidlight.github.io%2FDark-Family-War-Report%2F&label=Visitors&icon=github&color=4c1d95&labelColor=1f2937&style=for-the-badge&tz=US%2FEastern" class="h-5 mt-1">
                    </div>
                    <button id="mobile-menu-button" class="text-white">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16m-7 6h7"></path></svg>
                    </button>
                </div>
            </div>
            <aside id="sidebar" class="bg-gray-800 text-white w-64 space-y-6 py-7 px-2 absolute inset-y-0 left-0 transform -translate-x-full md:relative md:translate-x-0 transition duration-200 ease-in-out z-20 sidebar">
                <div class="hidden md:block px-2 pb-4 border-b border-gray-700">
                    <div class="text-xs text-gray-500">
                        <p>Generated on: {now.strftime('%Y-%m-%d %I:%M %p')}</p>
                        <div class="mt-2"><img src="https://hitscounter.dev/api/hit?url=https%3A%2F%2Fthelucidlight.github.io%2FDark-Family-War-Report%2F&label=Visitors&icon=github&color=4c1d95&labelColor=1f2937&style=for-the-badge&tz=US%2FEastern"></div>
                    </div>
                </div>
                <div class="flex items-center justify-between px-2">
                    <h1 class="text-xl font-bold text-purple-400">Dark Family</h1>
                     <button id="close-menu-button" class="md:hidden text-white">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </button>
                </div>
                <nav><ul class="space-y-2">{nav_links}</ul></nav>
            </aside>
            <main class="flex-1 overflow-y-auto">{clan_sections_html}</main>
        </div>
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                const sidebar = document.getElementById('sidebar');
                const mobileMenuButton = document.getElementById('mobile-menu-button');
                const closeMenuButton = document.getElementById('close-menu-button');
                const navLinks = document.querySelectorAll('.nav-link');
                const clanSections = document.querySelectorAll('.clan-section');
                function openSidebar() {{ sidebar.classList.remove('-translate-x-full'); }}
                function closeSidebar() {{ sidebar.classList.add('-translate-x-full'); }}
                mobileMenuButton.addEventListener('click', openSidebar);
                closeMenuButton.addEventListener('click', closeSidebar);
                navLinks.forEach(link => {{
                    link.addEventListener('click', function(e) {{
                        e.preventDefault();
                        navLinks.forEach(l => l.classList.remove('active'));
                        clanSections.forEach(s => s.classList.remove('active'));
                        this.classList.add('active');
                        document.getElementById(this.getAttribute('data-clan-target')).classList.add('active');
                        if (window.innerWidth < 768) {{ closeSidebar(); }}
                    }});
                }});
                const allTabBtns = document.querySelectorAll('.tab-btn');
                allTabBtns.forEach(btn => {{
                    btn.addEventListener('click', function() {{
                        const clanSection = this.closest('.clan-section');
                        const targetTabId = this.getAttribute('data-tab-target');
                        clanSection.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                        clanSection.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                        this.classList.add('active');
                        document.getElementById(targetTabId).classList.add('active');
                    }});
                }});
                navLinks.forEach(link => {{
                    link.className = 'nav-link block py-2.5 px-4 rounded transition duration-200 hover:bg-purple-700 hover:text-white';
                    if (document.getElementById(link.dataset.clanTarget).classList.contains('active')) {{
                        link.classList.add('active');
                    }}
                }});
            }});
        </script>
    </body>
    </html>
    """
    
    try:
        output_filename = "index.html"
        with open(output_filename, "w", encoding="utf-8") as f:
            f.write(html_template)
        print(f"\n\nMaster HTML report successfully saved to '{output_filename}'")
    except IOError as e:
        print(f"\nError: Could not save master report to file. {e}")

if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: CR_API_KEY environment variable not set. Please set it before running.")
    else:
        generate_master_html_report()

