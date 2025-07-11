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
        row['__sources_26'] = source_maps['2025-07-26'].get(seat, [])
        row['__sources_27'] = source_maps['2025-07-27'].get(seat, [])
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
        if row['Seat number'] in twoday_pass_rows:
            return ['background-color: #90EE90'] * (len(row)-4) + ['']*4  # light green for 2-day pass rows
        elif row['Seat number'] in mismatch_rows:
            return ['background-color: #fff3b0'] * (len(row)-4) + ['']*4  # yellow for mismatch rows
        return [''] * len(row)
    styled = df.style
    for day_col, source_col, name_source_col in zip(
        ['25th July (Name/s)', '26th July (Name/s)', '27th July (Name/s)'],
        [None, '__sources_26', '__sources_27'],
        [None, '__name_sources_26', '__name_sources_27']
    ):
        if source_col:
            styled = styled.apply(
                lambda col: [highlight_cell(val, seat, day_col, sources, name_sources, set(df.loc[i, '25th July (Name/s)'].split(', ')) if df.loc[i, '25th July (Name/s)'] else set())
                             for i, (val, seat, sources, name_sources) in enumerate(zip(col, df['Seat number'], df[source_col], df[name_source_col]))],
                axis=0, subset=[day_col])
        else:
            styled = styled.apply(lambda col: [highlight_cell(val, seat, day_col, [], [], set()) for val, seat in zip(col, df['Seat number'])], axis=0, subset=[day_col])
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
    # Row rendering
    for idx, row in enumerate(seat_map):
        row_label = row['row']
        # Side seats (right) - swapped to be on the right side
        right_seats = [s for s in row['side'] if int(s[len(row_label):]) % 2 == 0]
        # Center seats
        center_seats = row['center']
        # Side seats (left) - swapped to be on the left side
        left_seats = [s for s in row['side'] if int(s[len(row_label):]) % 2 == 1]
        # Row container
        row_html = '<div style="display:flex;align-items:center;justify-content:center;margin-bottom:2px;">'
        # Left side seats - sorted from aisle to outside (ascending order)
        for seat in sorted(left_seats, key=lambda x: int(x[len(row_label):]), reverse=True):
            seat_name, has_name = get_seat_data(seat)
            # Apply highlighting rules based on seat table data
            if row_label in ['GG', 'HH', 'JJ', 'KK', 'LL', 'MM']:
                color = '#ffa500'  # orange for all seats in rows GG-MM (highest priority)
            elif row_label == 'G' and seat in ['G108', 'G109', 'G110', 'G111', 'G112']:
                color = '#ffa500'  # orange for seats G108 to G112
            elif seat in ['Q12', 'Q14', 'Q16']:
                color = '#ffa500'  # orange for Q12, Q14, Q16
            elif has_name:
                color = '#4CAF50'  # green for seats with names
            elif row_label in ['A', 'B', 'C', 'D', 'E']:
                color = '#ff4d4d'  # red for vacant seats in rows A-E
            elif row_label == 'K':
                color = '#ffa500'  # orange for vacant seats in row K
            else:
                color = '#fff'     # white for all other vacant seats
            row_html += f'<div style="width:22px;height:22px;border:1px solid #888;margin:1px;background:{color};display:flex;align-items:center;justify-content:center;font-size:0.7em;"></div>'
        # Aisle between side and center
        if left_seats and center_seats:
            row_html += '<div style="width:18px;"></div>'
        # Center seats
        for seat in reversed(center_seats):
            seat_name, has_name = get_seat_data(seat)
            # Apply highlighting rules based on seat table data
            if row_label in ['GG', 'HH', 'JJ', 'KK', 'LL', 'MM']:
                color = '#ffa500'  # orange for all seats in rows GG-MM (highest priority)
            elif row_label == 'G' and seat in ['G108', 'G109', 'G110', 'G111', 'G112']:
                color = '#ffa500'  # orange for seats G108 to G112
            elif seat in ['Q12', 'Q14', 'Q16']:
                color = '#ffa500'  # orange for Q12, Q14, Q16
            elif has_name:
                color = '#4CAF50'  # green for seats with names
            elif row_label in ['A', 'B', 'C', 'D', 'E']:
                color = '#ff4d4d'  # red for vacant seats in rows A-E
            elif row_label == 'K':
                color = '#ffa500'  # orange for vacant seats in row K
            else:
                color = '#fff'     # white for all other vacant seats
            row_html += f'<div style="width:22px;height:22px;border:1px solid #888;margin:1px;background:{color};display:flex;align-items:center;justify-content:center;font-size:0.7em;"></div>'
        # Aisle between center and right side
        if right_seats and center_seats:
            row_html += '<div style="width:18px;"></div>'
        # Right side seats
        for seat in sorted(right_seats, key=lambda x: int(x[len(row_label):])):
            seat_name, has_name = get_seat_data(seat)
            # Apply highlighting rules based on seat table data
            if row_label in ['GG', 'HH', 'JJ', 'KK', 'LL', 'MM']:
                color = '#ffa500'  # orange for all seats in rows GG-MM (highest priority)
            elif row_label == 'G' and seat in ['G108', 'G109', 'G110', 'G111', 'G112']:
                color = '#ffa500'  # orange for seats G108 to G112
            elif seat in ['Q12', 'Q14', 'Q16']:
                color = '#ffa500'  # orange for Q12, Q14, Q16
            elif row_label in ['L', 'M', 'N', 'P'] and not has_name:
                color = '#ffa500'  # orange for vacant RHS seats in L, M, N, P
            elif has_name:
                color = '#4CAF50'  # green for seats with names
            elif row_label in ['A', 'B', 'C', 'D', 'E']:
                color = '#ff4d4d'  # red for vacant seats in rows A-E
            elif row_label == 'K':
                color = '#ffa500'  # orange for vacant seats in row K
            else:
                color = '#fff'     # white for all other vacant seats
            row_html += f'<div style="width:22px;height:22px;border:1px solid #888;margin:1px;background:{color};display:flex;align-items:center;justify-content:center;font-size:0.7em;"></div>'
        row_html += f'<span style="margin-left:8px;font-size:0.8em;color:#333;">{row_label}</span>'
        row_html += '</div>'
        st.markdown(row_html, unsafe_allow_html=True)
        # Aisle between K/L, V/AA, FF/GG, and BB/CC
        if row_label in ['K', 'V', 'FF', 'BB']:
            st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)

def main():
    st.title('NAFA Film Festival 2025 - Seat Allocation Overview')
    day_to_records = load_and_normalize()
    seat_df, double_booked, mismatch_rows, twoday_pass_rows = build_seat_table(day_to_records)
    tabs = st.tabs(["Seat Table", "Visual Seat Map"])
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