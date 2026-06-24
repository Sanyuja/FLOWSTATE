"""
content_db_updater.py
=====================
Merges CLIP tags + Claude refinements into master_content_db.xlsx.
Also exports content_inventory.json for the n8n trend scout workflow.

Run:
    python content_db_updater.py

Output:
    master_content_db.xlsx      (in project scripts folder)
    SCRIPTS_DIR/content_inventory.json  (for n8n trend scout)
"""

import os, json
import pandas as pd
import xlsxwriter
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_DIR    = os.environ.get("CONTENT_BASE",  "D:\\your-content-folder")
SCRIPTS_DIR = os.environ.get("SCRIPTS_DIR",   "D:\\your-content-folder\\scripts")

CLIP_OUTPUT     = os.path.join(BASE_DIR, "clip_tags_output.csv")
REFINED_OUTPUT  = os.path.join(BASE_DIR, "claude_refined_output.csv")
CAPTIONS_OUTPUT = os.path.join(BASE_DIR, "captions_output.csv")
MASTER_XLSX     = os.path.join(SCRIPTS_DIR, "master_content_db.xlsx")
INVENTORY_JSON  = os.path.join(SCRIPTS_DIR, "content_inventory.json")


# ── LOAD ──────────────────────────────────────────────────────────────────────
def load_sources():
    master = pd.DataFrame()
    if os.path.exists(MASTER_XLSX):
        print("[Load] Reading existing master DB...")
        try:
            master = pd.read_excel(MASTER_XLSX, sheet_name="Master DB")
            print(f"  Master DB: {len(master)} rows")
        except Exception as e:
            print(f"  [Warn] Could not read master DB: {e}. Starting fresh.")
    else:
        print("[Load] No existing master DB — will create from scratch.")

    clip_df = pd.DataFrame()
    if os.path.exists(CLIP_OUTPUT):
        clip_df = pd.read_csv(CLIP_OUTPUT)
        print(f"  CLIP output: {len(clip_df)} rows")
    else:
        print("  [Skip] No CLIP output found.")

    refined_df = pd.DataFrame()
    if os.path.exists(REFINED_OUTPUT):
        refined_df = pd.read_csv(REFINED_OUTPUT)
        print(f"  Claude refined: {len(refined_df)} rows")
    else:
        print("  [Skip] No Claude refined output found.")

    captions_df = pd.DataFrame()
    if os.path.exists(CAPTIONS_OUTPUT):
        captions_df = pd.read_csv(CAPTIONS_OUTPUT)
        print(f"  Captions: {len(captions_df)} rows")
    else:
        print("  [Skip] No captions output found.")

    return master, clip_df, refined_df, captions_df


# ── MERGE ─────────────────────────────────────────────────────────────────────
CLIP_COL_MAP = {
    "Vibe":"vibe","Outfit":"outfit","Pose":"pose","Activity":"activity",
    "Location":"location","Lighting":"lighting","Style":"style",
    "Face":"face_detected","X":"X","IG":"IG","Threads":"Threads",
    "Twitch":"Twitch","Reddit":"Reddit","OF":"OF",
}

REF_COL_MAP = {
    "Vibe":"vibe","Outfit":"outfit","Pose":"pose","Activity":"activity",
    "Location":"location","Lighting":"lighting","Style":"style",
    "X":"X","IG":"IG","Threads":"Threads","Twitch":"Twitch","Reddit":"Reddit","OF":"OF",
}


def merge_into_master(master, clip_df, refined_df, captions_df):
    # If no master exists yet, bootstrap from CLIP output
    if master.empty and not clip_df.empty:
        print("[Build] Bootstrapping master DB from CLIP output...")
        master = clip_df.rename(columns={
            "filename":     "Filename",
            "full_path":    "File_Path",
            "folder_label": "Category",
            "type":         "Type",
            "format":       "Format",
            "is_sensitive": "Sensitive",
        }).copy()
        master["Status"]   = "unlabeled"
        master["Tags"]     = ""
        master["Notes"]    = ""
        master["posted"]   = False

    df = master.copy()
    df["Filename_lower"] = df["Filename"].str.lower() if "Filename" in df.columns else pd.Series(dtype=str)

    # Merge CLIP labels for unlabeled rows
    if not clip_df.empty:
        clip_df["filename_lower"] = clip_df["filename"].str.lower()
        clip_map    = clip_df.set_index("filename_lower")
        clip_updated = 0

        for idx, row in df.iterrows():
            fn = row.get("Filename_lower", "")
            if fn in clip_map.index and str(row.get("Status","")) == "unlabeled":
                clip_row = clip_map.loc[fn]
                for master_col, clip_col in CLIP_COL_MAP.items():
                    val = clip_row.get(clip_col, "")
                    if pd.notna(val) and str(val).strip():
                        df.at[idx, master_col] = str(val)
                df.at[idx, "Status"] = "labeled"
                clip_updated += 1

        print(f"[Merge] CLIP: updated {clip_updated} rows")

    # Merge Claude refined labels for hero images
    if not refined_df.empty:
        refined_df["filename_lower"] = refined_df["filename"].str.lower()
        ref_map    = refined_df.set_index("filename_lower")
        ref_updated = 0

        for idx, row in df.iterrows():
            fn = row.get("Filename_lower", "")
            if fn in ref_map.index:
                ref_row = ref_map.loc[fn]
                for master_col, ref_col in REF_COL_MAP.items():
                    val = ref_row.get(ref_col, "")
                    if pd.notna(val) and str(val).strip():
                        df.at[idx, master_col] = str(val)
                df.at[idx, "Status"] = "confirmed"
                ref_updated += 1

        print(f"[Merge] Claude: updated {ref_updated} rows")

    df.drop(columns=["Filename_lower"], inplace=True, errors="ignore")
    return df, captions_df


# ── EXPORT INVENTORY JSON ─────────────────────────────────────────────────────
def export_inventory_json(master_df: pd.DataFrame):
    """Export lightweight JSON for the n8n trend scout workflow."""
    PLAT_COLS = ["X", "IG", "Threads", "Twitch", "Reddit", "OF"]
    EXPORT_COLS = [
        "Filename", "File_Path", "Category", "Type",
        "Vibe", "Outfit", "Activity", "Location", "Style",
        "Sensitive", "Status", "posted",
    ] + PLAT_COLS

    available = [c for c in EXPORT_COLS if c in master_df.columns]
    out_df    = master_df[available].copy()

    # Normalize booleans
    for col in PLAT_COLS:
        if col in out_df.columns:
            out_df[col] = out_df[col].apply(lambda v: v == "✓")

    if "Sensitive" in out_df.columns:
        out_df["is_sensitive"] = out_df["Sensitive"].apply(
            lambda v: str(v).upper() in ("YES", "TRUE", "1")
        )

    if "posted" not in out_df.columns:
        out_df["posted"] = out_df.get("Status", pd.Series()).apply(
            lambda v: str(v).lower() == "posted"
        )

    # Rename to lowercase for n8n consistency
    rename = {
        "Filename": "filename",
        "File_Path": "full_path",
        "Category": "folder_label",
        "Type": "type",
        "Vibe": "vibe",
        "Activity": "activity",
        "Location": "location",
        "Style": "style",
        "Status": "status",
    }
    out_df.rename(columns={k: v for k, v in rename.items() if k in out_df.columns}, inplace=True)

    records = out_df.to_dict("records")
    os.makedirs(os.path.dirname(INVENTORY_JSON), exist_ok=True)

    with open(INVENTORY_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

    print(f"[JSON] Exported {len(records)} records → {INVENTORY_JSON}")


# ── BUILD EXCEL ───────────────────────────────────────────────────────────────
DARK = '#1A1A2E'; MID = '#16213E'; ACCENT = '#E94560'; GOLD = '#F5A623'
MUTED = '#8892B0'; WHITE = '#FFFFFF'; GREEN = '#00C896'; HDR = '#0F3460'

def build_xlsx(master_df, captions_df, out_path):
    print(f"\n[Build] Writing {out_path}...")
    wb = xlsxwriter.Workbook(out_path, {'strings_to_urls': False})

    def fmt(bold=False, color=WHITE, bg=None, size=10, align='left'):
        d = {'font_name':'Calibri','font_size':size,'font_color':color,'bold':bold,
             'valign':'vcenter','align':align,'border':1,'border_color':'#DDDDDD'}
        if bg: d['bg_color'] = bg
        return wb.add_format(d)

    hdr_fmt  = fmt(bold=True, color=WHITE, bg=HDR, size=10, align='center')
    conf_fmt = fmt(color='#155724', bg='#E8F5E9', size=9)
    lbl_fmt  = fmt(color='#856404', bg='#FFFDE7', size=9)
    unl_fmt  = fmt(color='#444444', bg='#FAFAFA', size=9)
    sens_fmt = fmt(color='#7B0000', bg='#FFE8EF', size=9)
    tick_fmt = fmt(bold=True, color='#007B55', bg='#F0FFF8', size=11, align='center')

    # Dashboard
    ws = wb.add_worksheet('Dashboard')
    ws.hide_gridlines(2)
    for col in 'BCDEFGHIJ': ws.set_column(f'{col}:{col}', 18)

    title_fmt = wb.add_format({'font_name':'Calibri','font_size':18,'bold':True,
        'font_color':ACCENT,'bg_color':DARK,'align':'center','valign':'vcenter'})
    sub_fmt = wb.add_format({'font_name':'Calibri','font_size':9,'italic':True,
        'font_color':MUTED,'bg_color':DARK,'align':'center','valign':'vcenter'})
    stat_lbl = wb.add_format({'font_name':'Calibri','font_size':8,'font_color':MUTED,
        'bg_color':MID,'align':'center','valign':'vcenter'})
    stat_val = wb.add_format({'font_name':'Calibri','font_size':20,'bold':True,
        'font_color':GOLD,'bg_color':MID,'align':'center','valign':'vcenter'})
    grn_fmt = wb.add_format({'font_name':'Calibri','font_size':16,'bold':True,
        'font_color':GREEN,'bg_color':MID,'align':'center','valign':'vcenter'})

    ws.set_row(1, 36); ws.set_row(2, 18); ws.set_row(4, 16); ws.set_row(5, 34)
    ws.merge_range('B2:I2', 'FLOWSTATE — Content Database', title_fmt)
    ws.merge_range('B3:I3', f'Updated: {datetime.now().strftime("%B %d, %Y")}', sub_fmt)

    total     = len(master_df)
    photos    = (master_df['Type'] == 'photo').sum()    if 'Type'   in master_df.columns else 0
    videos    = (master_df['Type'] == 'video').sum()    if 'Type'   in master_df.columns else 0
    confirmed = (master_df['Status'] == 'confirmed').sum() if 'Status' in master_df.columns else 0
    sensitive = (master_df['Sensitive'] == 'YES').sum() if 'Sensitive' in master_df.columns else 0

    stats = [('Total', total), ('Photos', photos), ('Videos', videos),
             ('Confirmed', confirmed), ('Sensitive', sensitive), ('SFW', total - sensitive)]
    for i, (lbl, val) in enumerate(stats):
        c = 'BCDEFG'[i]
        ws.write(f'{c}5', lbl, stat_lbl)
        ws.write(f'{c}6', val, stat_val)

    ws.set_row(8, 22)
    sec_fmt = wb.add_format({'font_name':'Calibri','font_size':11,'bold':True,
        'font_color':WHITE,'bg_color':HDR,'align':'left','valign':'vcenter'})
    ws.merge_range('B9:I9', 'Platform Routing', sec_fmt)
    plat_info = [('X','X'),('Instagram','IG'),('Threads','Threads'),
                 ('Twitch','Twitch'),('Reddit','Reddit'),('OnlyFans','OF')]
    ws.set_row(9, 18); ws.set_row(10, 28)
    for i, (lbl, col) in enumerate(plat_info):
        c = 'BCDEFG'[i]
        cnt = (master_df[col] == '✓').sum() if col in master_df.columns else 0
        ws.write(f'{c}10', lbl, stat_lbl)
        ws.write(f'{c}11', cnt, grn_fmt)

    # Master DB sheet
    ws_main = wb.add_worksheet('Master DB')
    ws_main.hide_gridlines(2); ws_main.freeze_panes(1, 0); ws_main.set_zoom(90)

    col_widths = {
        'Filename':35,'Category':22,'Type':7,'Format':7,'Size_MB':8,'Status':11,
        'Sensitive':9,'Face':6,'Vibe':18,'Outfit':13,'Pose':13,'Activity':15,
        'Location':17,'Lighting':13,'Style':13,'Tags':22,'Notes':22,
        'X':4,'IG':4,'Threads':8,'Twitch':7,'Reddit':7,'OF':4,'File_Path':50
    }
    PLAT_SET = {'X','IG','Threads','Twitch','Reddit','OF'}

    cols_out = list(master_df.columns)
    ws_main.set_row(0, 26)
    for c_idx, col in enumerate(cols_out):
        ws_main.set_column(c_idx, c_idx, col_widths.get(col, 15))
        ws_main.write(0, c_idx, col, hdr_fmt)

    for r_idx, row in enumerate(master_df.itertuples(index=False), 1):
        status = str(getattr(row, 'Status', 'unlabeled'))
        sens   = str(getattr(row, 'Sensitive', '')) == 'YES'
        rf     = sens_fmt if sens else (conf_fmt if status == 'confirmed' else (lbl_fmt if status == 'labeled' else unl_fmt))
        ws_main.set_row(r_idx, 15)
        for c_idx, col in enumerate(cols_out):
            val = getattr(row, col, '')
            val = str(val) if pd.notna(val) and val else ''
            ws_main.write(r_idx, c_idx, val, tick_fmt if col in PLAT_SET and val == '✓' else rf)

    # Captions sheet
    if not captions_df.empty:
        ws_cap = wb.add_worksheet('Captions')
        ws_cap.hide_gridlines(2); ws_cap.freeze_panes(1, 0)
        cap_widths = {'filename':35,'folder_label':22,'caption_X':60,'caption_IG':70,
                      'caption_Threads':60,'caption_OF':60}
        cap_cols = list(captions_df.columns)
        ws_cap.set_row(0, 26)
        for c, col in enumerate(cap_cols):
            ws_cap.set_column(c, c, cap_widths.get(col, 30))
            ws_cap.write(0, c, col, hdr_fmt)
        cap_row_fmt = wb.add_format({'font_name':'Calibri','font_size':9,'font_color':'#222222',
            'bg_color':'#F8F8FF','border':1,'border_color':'#DDDDDD','valign':'vcenter','text_wrap':True})
        for r, row in enumerate(captions_df.itertuples(index=False), 1):
            ws_cap.set_row(r, 40)
            for c, col in enumerate(cap_cols):
                val = getattr(row, col, '')
                ws_cap.write(r, c, str(val) if pd.notna(val) and val else '', cap_row_fmt)

    wb.close()
    print(f"[Done] Saved: {out_path}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  FLOWSTATE — Content DB Updater")
    print("=" * 60)

    master, clip_df, refined_df, captions_df = load_sources()
    updated_master, captions_df = merge_into_master(master, clip_df, refined_df, captions_df)

    print(f"\n[Summary]")
    if "Status" in updated_master.columns:
        print(f"  Confirmed: {(updated_master['Status'] == 'confirmed').sum()}")
        print(f"  Labeled:   {(updated_master['Status'] == 'labeled').sum()}")
        print(f"  Unlabeled: {(updated_master['Status'] == 'unlabeled').sum()}")

    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    build_xlsx(updated_master, captions_df, MASTER_XLSX)
    export_inventory_json(updated_master)

    print(f"\nmaster_content_db.xlsx updated.")
    print(f"content_inventory.json ready for the n8n Trend Scout workflow.")


if __name__ == "__main__":
    main()
