"""
Import masters programs data from Excel into SQLite database
"""
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent / "career_tree.db"
EXCEL_PATH = Path(__file__).parent.parent / "Masters_Programs_Global_Rankings.xlsx"

def assign_funding_tier(row):
    """Assign funding tier based on tuition and country"""
    tuition = row['Tuition ($K)']
    country = row['Country']
    tier = row['Tier']

    if tuition <= 5 and country in ['Germany', 'Norway', 'Austria', 'Finland', 'Denmark',
                                     'Sweden', 'Czech Republic', 'Poland', 'Switzerland']:
        return 'tier1_free_europe'
    elif country == 'USA' and tier == 'Tier 1':
        return 'tier2_elite_us'
    elif country in ['Canada', 'UK', 'Netherlands', 'France', 'Belgium', 'Italy', 'Spain',
                     'Portugal', 'Australia', 'New Zealand', 'Switzerland', 'Israel'] or \
         (country == 'USA' and tier in ['Tier 2', 'Mid-Tier']):
        return 'tier3_midtier_global'
    else:
        return 'tier4_asia_regional'

def import_masters_programs():
    """Import all masters programs from Excel into database"""

    # Read Excel data
    df = pd.read_excel(EXCEL_PATH, sheet_name='All Programs', header=1)
    df = df.dropna(how='all')
    df = df[df['Country'].notna()].copy()

    # Assign funding tiers
    df['funding_tier'] = df.apply(assign_funding_tier, axis=1)

    print(f"📊 Importing {len(df)} programs from Excel...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute("DELETE FROM programs")
    cursor.execute("DELETE FROM universities")

    universities = {}  # Cache: (name, country) -> id

    for idx, row in df.iterrows():
        # Insert or get university
        uni_key = (row['University'], row['Country'])

        if uni_key not in universities:
            cursor.execute("""
                INSERT INTO universities (name, country, region, tier)
                VALUES (?, ?, ?, ?)
            """, (
                row['University'],
                row['Country'],
                row['Region'],
                row['Tier']
            ))
            universities[uni_key] = cursor.lastrowid

        uni_id = universities[uni_key]

        # Insert program
        cursor.execute("""
            INSERT INTO programs (
                university_id, program_name, field, tuition_usd,
                y1_salary_usd, y5_salary_usd, y10_salary_usd, p90_y10_usd,
                net_10yr_usd, funding_tier, primary_market, key_employers,
                notes, data_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uni_id,
            row['Program / Degree'],
            row['Field'],
            int(row['Tuition ($K)']) if pd.notna(row['Tuition ($K)']) else None,
            int(row['Y1 TC ($K)']) if pd.notna(row['Y1 TC ($K)']) else None,
            int(row['Y5 TC ($K)']) if pd.notna(row['Y5 TC ($K)']) else None,
            int(row['Y10 TC ($K)']) if pd.notna(row['Y10 TC ($K)']) else None,
            int(row['P90 Y10 ($K)']) if pd.notna(row['P90 Y10 ($K)']) else None,
            int(row['Net 10yr Cum ($K)']) if pd.notna(row['Net 10yr Cum ($K)']) else None,
            row['funding_tier'],
            row['Primary Market'] if pd.notna(row['Primary Market']) else None,
            row['Key Employers'] if pd.notna(row['Key Employers']) else None,
            row['Notes'] if pd.notna(row['Notes']) else None,
            row['Data Confidence'] if pd.notna(row['Data Confidence']) else None
        ))

    conn.commit()

    # Print summary
    cursor.execute("SELECT COUNT(*) FROM universities")
    uni_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM programs")
    prog_count = cursor.fetchone()[0]

    cursor.execute("SELECT funding_tier, COUNT(*) FROM programs GROUP BY funding_tier")
    tier_counts = cursor.fetchall()

    print(f"\n✅ Import complete!")
    print(f"   📚 {uni_count} universities")
    print(f"   🎓 {prog_count} programs")
    print(f"\n   By funding tier:")
    for tier, count in tier_counts:
        print(f"      {tier}: {count}")

    conn.close()

if __name__ == "__main__":
    import_masters_programs()
