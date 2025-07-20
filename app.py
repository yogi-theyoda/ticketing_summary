import streamlit as st
import pandas as pd
import os
from collections import defaultdict
import re

st.set_page_config(layout='wide')

# File paths
DATA_DIR = 'data'
MASTER_SEAT_MAP = os.path.join(DATA_DIR, 'master_seat_map.csv')
FILES = {
    '25': ('25.csv', '2025-07-25'),
    '26': ('26.csv', '2025-07-26'),
    '27': ('27.csv', '2025-07-27'),
    '2days': ('2 days.csv', ['2025-07-26', '2025-07-27'])
}

# Helper to get full name
def get_full_name(row):
    return f"{row['First Name']} {row['Last Name']}".strip()

def load_and_normalize():
    day_to_records = defaultdict(list)
    # Process 25, 26, 27
    for key in ['25', '26', '27']:
        file, date = FILES[key]
        df = pd.read_csv(os.path.join(DATA_DIR, file))
        for _, row in df.iterrows():
            record = row.to_dict()
            record['__date'] = date
            record['__source'] = key  # Track source file
            day_to_records[date].append(record)
    # Process 2 days.csv
    file, dates = FILES['2days']
    df = pd.read_csv(os.path.join(DATA_DIR, file))
    for _, row in df.iterrows():
        for date in dates:
            record = row.to_dict()
            record['__date'] = date
            record['__source'] = '2days'
            day_to_records[date].append(record)
    return day_to_records

def generate_master_seat_map():
    master_df = pd.read_csv(MASTER_SEAT_MAP)
    seat_map = []
    for _, row in master_df.iterrows():
        row_label = str(row['Row'])
        # Center seats
        try:
            center_start = int(row['Center Start'])
            center_end = int(row['Center End'])
            center_seats = [f"{row_label}{num}" for num in range(center_start, center_end + 1)]
        except:
            center_seats = []
        # Side seats
        try:
            side_start = int(row['Sides Start'])
            side_end = int(row['Sides End'])
            if side_start != 0 and side_end != 0:
                side_seats = [f"{row_label}{num}" for num in range(side_start, side_end + 1)]
            else:
                side_seats = []
        except:
            side_seats = []
        seat_map.append({
            'row': row_label,
            'center': center_seats,
            'side': side_seats
        })
    return seat_map

def generate_master_seat_list():
    seat_map = generate_master_seat_map()
    seat_list = []
    for row in seat_map:
        seat_list.extend(row['center'])
        seat_list.extend(row['side'])
    return seat_list

def organize_seats(day_records):
    seat_to_names = defaultdict(list)
    seat_to_sources = defaultdict(list)
    seat_to_name_sources = defaultdict(list)  # (name, source) for each seat
    unallocated = []
    for rec in day_records:
        name = get_full_name(rec)
        seats = str(rec.get('Seats', '')).strip()
        source = rec.get('__source', '')
        if not seats or seats.lower() == 'nan':
            unallocated.append(name)
            continue
        for seat in [s.strip() for s in seats.split(',') if s.strip()]:
            seat_to_names[seat].append(name)
            seat_to_sources[seat].append(source)
            seat_to_name_sources[seat].append((name, source))
    return seat_to_names, seat_to_sources, seat_to_name_sources, unallocated

def seat_sort_key(seat):
    m = re.fullmatch(r'([A-Z]{1,2})(\d+)', seat)
    if m:
        prefix = m.group(1)
        number = int(m.group(2))
        return (0 if len(prefix) == 1 else 1, prefix, number)
    return (2, seat)

def build_seat_table(day_to_records):
    seat_maps = {}
    source_maps = {}
    name_source_maps = {}
    master_seat_list = generate_master_seat_list()
    day_keys = ['2025-07-25', '2025-07-26', '2025-07-27']
    for day, key in zip(day_keys, ['25', '26', '27']):
        seat_to_names, seat_to_sources, seat_to_name_sources, _ = organize_seats(day_to_records[day])
        seat_maps[day] = seat_to_names
        source_maps[day] = seat_to_sources
        name_source_maps[day] = seat_to_name_sources
    rows = []
    mismatch_rows = set()
    twoday_pass_rows = set()  # Track rows that need 2-day pass highlighting
    for seat in master_seat_list:
        row = {'Seat number': seat}
        names_25 = set(seat_maps['2025-07-25'].get(seat, []))
        names_26 = set(seat_maps['2025-07-26'].get(seat, []))
        names_27 = set(seat_maps['2025-07-27'].get(seat, []))
        
        # Check if seat is occupied on both 26th & 27th July by 2-day pass tickets but vacant on 25th July
        has_2day_pass_26 = '2days' in source_maps['2025-07-26'].get(seat, [])
        has_2day_pass_27 = '2days' in source_maps['2025-07-27'].get(seat, [])
        both_26_27_occupied = names_26 and names_27 and names_26 == names_27
        vacant_25 = not names_25
        
        # If both 26th & 27th are occupied by same person with 2-day pass and 25th is vacant
        if both_26_27_occupied and has_2day_pass_26 and has_2day_pass_27 and vacant_25:
            # Fill in 25th July with the same name as 26th & 27th July
            names_25 = names_26  # Use the same names
            twoday_pass_rows.add(seat)
        
        row['25th July (Name/s)'] = ', '.join(names_25) if names_25 else ''
        row['26th July (Name/s)'] = ', '.join(names_26) if names_26 else ''
        row['27th July (Name/s)'] = ', '.join(names_27) if names_27 else ''
        # Track sources for cell highlighting
        row['__sources_25'] = source_maps['2025-07-25'].get(seat, [])
        row['__sources_26'] = source_maps['2025-07-26'].get(seat, [])
        row['__sources_27'] = source_maps['2025-07-27'].get(seat, [])
        row['__name_sources_25'] = name_source_maps['2025-07-25'].get(seat, [])
        row['__name_sources_26'] = name_source_maps['2025-07-26'].get(seat, [])
        row['__name_sources_27'] = name_source_maps['2025-07-27'].get(seat, [])
        # Highlight if 25th July and (26th or 27th) have names and mismatch
        if names_25 and ((names_26 and names_25 != names_26) or (names_27 and names_25 != names_27)):
            mismatch_rows.add(seat)
        rows.append(row)
    df = pd.DataFrame(rows)
    double_booked = {day: {seat for seat, names in seat_maps[day].items() if len(names) > 1} for day in day_keys}
    return df, double_booked, mismatch_rows, twoday_pass_rows

def style_seat_table(df, double_booked, mismatch_rows, twoday_pass_rows):
    def highlight_cell(val, seat, day_col, sources, name_sources, names_25):
        col_to_day = {
            '25th July (Name/s)': '2025-07-25',
            '26th July (Name/s)': '2025-07-26',
            '27th July (Name/s)': '2025-07-27',
        }
        # Double-booked highlight
        if val and seat in double_booked.get(col_to_day[day_col], set()):
            return 'background-color: #ffcccc'
        # 25th July highlight (light yellow)
        if day_col == '25th July (Name/s)' and '25' in sources:
            return 'background-color: #fff2cc'
        # 26th July highlight (light blue)
        if day_col == '26th July (Name/s)' and '26' in sources:
            return 'background-color: #cce6ff'
        # 27th July highlight (light green)
        if day_col == '27th July (Name/s)' and '27' in sources:
            return 'background-color: #d6f5d6'
        # 2days source highlight (orange) if blank or different from 25th July
        if day_col in ['26th July (Name/s)', '27th July (Name/s)']:
            for name, source in name_sources:
                if source == '2days':
                    if not names_25 or name not in names_25:
                        return 'background-color: #ffd699'  # orange
        return ''
    def highlight_row(row):
        # Always highlight GG-MM rows in orange
        row_prefix = ''.join([c for c in row['Seat number'] if c.isalpha()])
        if row_prefix in ['GG', 'HH', 'JJ', 'KK', 'LL', 'MM']:
            return ['background-color: #ffa500'] * (len(row)-4) + ['']*4
        if row['Seat number'] in twoday_pass_rows:
            return ['background-color: #90EE90'] * (len(row)-4) + ['']*4  # light green for 2-day pass rows
        elif row['Seat number'] in mismatch_rows:
            return ['background-color: #fff3b0'] * (len(row)-4) + ['']*4  # yellow for mismatch rows
        return [''] * len(row)
    styled = df.style
    for day_col, source_col, name_source_col in zip(
        ['25th July (Name/s)', '26th July (Name/s)', '27th July (Name/s)'],
        ['__sources_25', '__sources_26', '__sources_27'],
        ['__name_sources_25', '__name_sources_26', '__name_sources_27']
    ):
        styled = styled.apply(
            lambda col: [highlight_cell(val, seat, day_col, sources, name_sources, set(df.loc[i, '25th July (Name/s)'].split(', ')) if df.loc[i, '25th July (Name/s)'] else set())
                         for i, (val, seat, sources, name_sources) in enumerate(zip(col, df['Seat number'], df[source_col], df[name_source_col]))],
            axis=0, subset=[day_col])
    styled = styled.apply(highlight_row, axis=1)
    return styled

def render_seat_map(seat_map, seat_df, day_label, seat_to_sources, seat_to_name_sources, day_choice):
    st.markdown(f"### {day_label} - Visual Seat Map")
    
    # Helper function to get seat data from table
    def get_seat_data(seat_number):
        seat_row = seat_df[seat_df['Seat number'] == seat_number]
        if seat_row.empty:
            return '', False
        if day_choice == '2025-07-25':
            return seat_row.iloc[0]['25th July (Name/s)'], bool(seat_row.iloc[0]['25th July (Name/s)'])
        elif day_choice == '2025-07-26':
            return seat_row.iloc[0]['26th July (Name/s)'], bool(seat_row.iloc[0]['26th July (Name/s)'])
        elif day_choice == '2025-07-27':
            return seat_row.iloc[0]['27th July (Name/s)'], bool(seat_row.iloc[0]['27th July (Name/s)'])
        return '', False
    
    # Stage block
    st.markdown('<div style="width:100%;text-align:center;font-size:1.2em;font-weight:bold;background:#333;color:#fff;padding:8px 0;margin-bottom:10px;">STAGE</div>', unsafe_allow_html=True)

    # --- Custom HTML+JS seat map with tooltips ---
    import streamlit.components.v1 as components
    seat_map_html = """
    <style>
    .seat-row { display: flex; align-items: center; justify-content: center; margin-bottom: 2px; }
    .seat-box { width: 22px; height: 22px; border: 1px solid #888; margin: 1px; display: flex; align-items: center; justify-content: center; font-size: 0.7em; position: relative; background: #fff; cursor: pointer; }
    .seat-label { margin-left: 8px; font-size: 0.8em; color: #333; }
    .aisle { width: 18px; }
    .tooltip {
      visibility: hidden;
      background: #222;
      color: #fff;
      text-align: center;
      border-radius: 4px;
      padding: 2px 8px;
      position: absolute;
      z-index: 10;
      bottom: 120%;
      left: 50%;
      transform: translateX(-50%);
      font-size: 16px;
      white-space: nowrap;
      opacity: 0;
      transition: opacity 0.2s;
      pointer-events: none;
    }
    .seat-box:hover .tooltip {
      visibility: visible;
      opacity: 1;
    }
    .tooltip-below {
      bottom: auto !important;
      top: 120%;
    }
    </style>
    <div id="seatmap-outer">
    """
    for idx, row in enumerate(seat_map):
        row_label = row['row']
        right_seats = [s for s in row['side'] if int(s[len(row_label):]) % 2 == 0]
        center_seats = row['center']
        left_seats = [s for s in row['side'] if int(s[len(row_label):]) % 2 == 1]
        special_orange_seats = set(['L3','L5','L7','L9','L11','L13','M3','M5','M7','M9','M11','M13','M15','N3','N5','N7','N9','N11','N13','N15'])
        # Remove LHS of M/N and L3 from special_orange_seats for blocking
        unblocked_seats = set()
        if row_label == 'M':
            unblocked_seats.update([f'M{n}' for n in range(1, 16, 2)])
        if row_label == 'N':
            unblocked_seats.update([f'N{n}' for n in range(1, 16, 2)])
        if row_label == 'L':
            unblocked_seats.add('L3')
        seat_map_html += '<div class="seat-row">'
        tooltip_class = 'tooltip-below' if idx == 0 else ''
        # Left side seats
        for seat in sorted(left_seats, key=lambda x: int(x[len(row_label):]), reverse=True):
            seat_name, has_name = get_seat_data(seat)
            # Always highlight GG-MM rows in orange
            if row_label in ['GG', 'HH', 'JJ', 'KK', 'LL', 'MM']:
                color = '#ffa500'
                blocked = True
            # Check if seat has a booking first
            elif has_name:
                color = '#4CAF50'
                blocked = False
            # Then check if it's unblocked (but not booked)
            elif seat in unblocked_seats:
                color = '#fff'
                blocked = False
            elif row_label == 'G' and seat in ['G108', 'G109', 'G110', 'G111', 'G112']:
                color = '#ffa500'
                blocked = True
            elif day_choice == '2025-07-25' and seat in ['Q12', 'Q14', 'Q16']:
                color = '#ffa500'
                blocked = True
            elif day_choice in ['2025-07-25', '2025-07-27'] and seat in special_orange_seats:
                color = '#ffa500'
                blocked = True
            elif row_label in ['A', 'B', 'C', 'D', 'E']:
                color = '#ff4d4d'
                blocked = True
            elif row_label == 'K':
                color = '#ffa500'
                blocked = True
            else:
                color = '#fff'
                blocked = False
            if has_name:
                tooltip_text = f"Row {row_label}, Seat {seat} — Name(s): {seat_name}"
            elif blocked:
                tooltip_text = f"Row {row_label}, Seat {seat} — Blocked"
            else:
                tooltip_text = f"Row {row_label}, Seat {seat} — Available"
            seat_map_html += f'<div class="seat-box" style="background:{color};"><span class="tooltip {tooltip_class}">{tooltip_text}</span></div>'
        if left_seats and center_seats:
            seat_map_html += '<div class="aisle"></div>'
        for seat in reversed(center_seats):
            seat_name, has_name = get_seat_data(seat)
            # Always highlight GG-MM rows in orange
            if row_label in ['GG', 'HH', 'JJ', 'KK', 'LL', 'MM']:
                color = '#ffa500'
                blocked = True
            elif has_name:
                color = '#4CAF50'
                blocked = False
            elif seat in unblocked_seats:
                color = '#fff'
                blocked = False
            elif row_label == 'G' and seat in ['G108', 'G109', 'G110', 'G111', 'G112']:
                color = '#ffa500'
                blocked = True
            elif day_choice == '2025-07-25' and seat in ['Q12', 'Q14', 'Q16']:
                color = '#ffa500'
                blocked = True
            elif day_choice in ['2025-07-25', '2025-07-27'] and seat in special_orange_seats:
                color = '#ffa500'
                blocked = True
            elif row_label in ['A', 'B', 'C', 'D', 'E']:
                color = '#ff4d4d'
                blocked = True
            elif row_label == 'K':
                color = '#ffa500'
                blocked = True
            else:
                color = '#fff'
                blocked = False
            if has_name:
                tooltip_text = f"Row {row_label}, Seat {seat} — Name(s): {seat_name}"
            elif blocked:
                tooltip_text = f"Row {row_label}, Seat {seat} — Blocked"
            else:
                tooltip_text = f"Row {row_label}, Seat {seat} — Available"
            seat_map_html += f'<div class="seat-box" style="background:{color};"><span class="tooltip {tooltip_class}">{tooltip_text}</span></div>'
        if right_seats and center_seats:
            seat_map_html += '<div class="aisle"></div>'
        for seat in sorted(right_seats, key=lambda x: int(x[len(row_label):])):
            seat_name, has_name = get_seat_data(seat)
            # Always highlight GG-MM rows in orange
            if row_label in ['GG', 'HH', 'JJ', 'KK', 'LL', 'MM']:
                color = '#ffa500'
                blocked = True
            elif has_name:
                color = '#4CAF50'
                blocked = False
            elif seat in unblocked_seats:
                color = '#fff'
                blocked = False
            elif row_label == 'G' and seat in ['G108', 'G109', 'G110', 'G111', 'G112']:
                color = '#ffa500'
                blocked = True
            elif day_choice == '2025-07-25' and seat in ['Q12', 'Q14', 'Q16']:
                color = '#ffa500'
                blocked = True
            elif day_choice == '2025-07-25' and row_label in ['L', 'M', 'N', 'P'] and not has_name:
                color = '#ffa500'
                blocked = True
            elif day_choice in ['2025-07-25', '2025-07-27'] and seat in special_orange_seats:
                color = '#ffa500'
                blocked = True
            elif row_label in ['A', 'B', 'C', 'D', 'E']:
                color = '#ff4d4d'
                blocked = True
            elif row_label == 'K':
                color = '#ffa500'
                blocked = True
            else:
                color = '#fff'
                blocked = False
            if has_name:
                tooltip_text = f"Row {row_label}, Seat {seat} — Name(s): {seat_name}"
            elif blocked:
                tooltip_text = f"Row {row_label}, Seat {seat} — Blocked"
            else:
                tooltip_text = f"Row {row_label}, Seat {seat} — Available"
            seat_map_html += f'<div class="seat-box" style="background:{color};"><span class="tooltip {tooltip_class}">{tooltip_text}</span></div>'
        seat_map_html += f'<span class="seat-label" title="Row {row_label}">{row_label}</span>'
        seat_map_html += '</div>'
        if row_label in ['K', 'V', 'FF', 'BB']:
            seat_map_html += '<div style="height:12px;"></div>'
    seat_map_html += '</div>'
    components.html(seat_map_html, height=700, scrolling=True)

    # Gallery groupings
    gallery_map = {
        'Celebrity Gallery': [chr(x) for x in range(ord('A'), ord('K')+1)],
        'Orchestra Gallery': [chr(x) for x in range(ord('L'), ord('V')+1)],
        'Mezzanine Level': ['AA', 'BB', 'CC', 'DD', 'EE', 'FF'],
        'Balcony': ['GG', 'HH', 'JJ', 'KK', 'LL', 'MM']
    }
    # For double-letter rows in Orchestra
    gallery_map['Orchestra Gallery'] += ['AA', 'BB', 'CC', 'DD', 'EE', 'FF'] if False else []  # not needed, handled above

    # Prepare color logic for counting
    special_orange_seats = set(['L3','L5','L7','L9','L11','L13','M3','M5','M7','M9','M11','M13','M15','N3','N5','N7','N9','N11','N13','N15'])
    booked_count = {g: 0 for g in gallery_map}
    blocked_count = {g: 0 for g in gallery_map}
    available_count = {g: 0 for g in gallery_map}

    # Build a mapping from row to gallery
    row_to_gallery = {}
    for gallery, rows in gallery_map.items():
        for r in rows:
            row_to_gallery[r] = gallery

    # Count seats by color for this day
    seat_map_data = generate_master_seat_map()
    for row in seat_map_data:
        row_label = row['row']
        gallery = row_to_gallery.get(row_label)
        if not gallery:
            continue
        # Side seats (right) - swapped to be on the right side
        right_seats = [s for s in row['side'] if int(s[len(row_label):]) % 2 == 0]
        # Center seats
        center_seats = row['center']
        # Side seats (left) - swapped to be on the left side
        left_seats = [s for s in row['side'] if int(s[len(row_label):]) % 2 == 1]
        # All seats in row
        all_seats = list(left_seats) + list(center_seats) + list(right_seats)
        for seat in all_seats:
            seat_name, has_name = get_seat_data(seat)
            color = None
            if row_label in ['GG', 'HH', 'JJ', 'KK', 'LL', 'MM']:
                color = 'orange'
            elif row_label == 'G' and seat in ['G108', 'G109', 'G110', 'G111', 'G112']:
                color = 'orange'
            elif day_choice == '2025-07-25' and seat in ['Q12', 'Q14', 'Q16']:
                color = 'orange'
            elif day_choice in ['2025-07-25', '2025-07-27'] and seat in special_orange_seats:
                color = 'orange'
            elif has_name:
                color = 'green'
            elif row_label in ['A', 'B', 'C', 'D', 'E']:
                color = 'red'
            elif row_label == 'K':
                color = 'orange'
            elif day_choice == '2025-07-25' and row_label in ['L', 'M', 'N', 'P'] and seat in right_seats and not has_name:
                color = 'orange'
            else:
                color = 'none'
            if color == 'green':
                booked_count[gallery] += 1
            elif color == 'orange' or color == 'red':
                blocked_count[gallery] += 1
            else:
                available_count[gallery] += 1

    # Show legend
    st.markdown("""
    <div style='display:flex;gap:24px;margin-bottom:8px;'>
      <span style='display:flex;align-items:center;gap:4px;'><span style='display:inline-block;width:18px;height:18px;background:#4CAF50;border:1px solid #888;'></span>Booked (Green)</span>
      <span style='display:flex;align-items:center;gap:4px;'><span style='display:inline-block;width:18px;height:18px;background:#ffa500;border:1px solid #888;'></span>Blocked (Orange)</span>
      <span style='display:flex;align-items:center;gap:4px;'><span style='display:inline-block;width:18px;height:18px;background:#ff4d4d;border:1px solid #888;'></span>Blocked (Red)</span>
      <span style='display:flex;align-items:center;gap:4px;'><span style='display:inline-block;width:18px;height:18px;background:#fff;border:1px solid #888;'></span>Available (No highlight)</span>
    </div>
    """, unsafe_allow_html=True)

    # Show summary table
    st.markdown("<b>Gallery Seat Summary for this day</b>", unsafe_allow_html=True)
    st.table({
        'Gallery': list(gallery_map.keys()),
        'Booked (Green)': [booked_count[g] for g in gallery_map],
        'Blocked (Orange/Red)': [blocked_count[g] for g in gallery_map],
        'Available': [available_count[g] for g in gallery_map],
    })

def main():
    st.title('NAFA Film Festival 2025 - Seat Allocation Overview')
    day_to_records = load_and_normalize()
    seat_df, double_booked, mismatch_rows, twoday_pass_rows = build_seat_table(day_to_records)
    tabs = st.tabs(["Seat Table", "Visual Seat Map"])  # Remove Tickets Report tab
    with tabs[0]:
        st.subheader('Seat Assignment Table')
        st.dataframe(style_seat_table(seat_df, double_booked, mismatch_rows, twoday_pass_rows), use_container_width=True)
        # Unallocated names per day
        st.subheader('Names with no seat allocated (per day)')
        day_labels = {'2025-07-25': '25th July', '2025-07-26': '26th July', '2025-07-27': '27th July'}
        for day in ['2025-07-25', '2025-07-26', '2025-07-27']:
            _, _, _, unallocated = organize_seats(day_to_records[day])
            if unallocated:
                st.error(f"{day_labels[day]}: ")
                for name in unallocated:
                    st.write(f"- {name}")
            else:
                st.info(f"{day_labels[day]}: All names have seat allocations.")
    with tabs[1]:
        day_labels = {'2025-07-25': '25th July', '2025-07-26': '26th July', '2025-07-27': '27th July'}
        day_choice = st.selectbox('Select Day', list(day_labels.keys()), format_func=lambda x: day_labels[x])
        seat_map = generate_master_seat_map()
        seat_to_names, seat_to_sources, seat_to_name_sources, _ = organize_seats(day_to_records[day_choice])
        render_seat_map(seat_map, seat_df, day_labels[day_choice], seat_to_sources, seat_to_name_sources, day_choice)

if __name__ == '__main__':
    main() 