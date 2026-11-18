"""Keep rows with valid reported latitude and longitude; never promote estimates."""
import csv, math, sys
from pathlib import Path

def clean(source, dest):
    total=kept=0
    with open(source,encoding='utf-8-sig',newline='') as inp, open(dest,'w',encoding='utf-8',newline='') as out:
        reader=csv.DictReader(inp); writer=csv.DictWriter(out,fieldnames=reader.fieldnames);writer.writeheader()
        for row in reader:
            total+=1
            try: lat,lon=float(row['latitude']),float(row['longitude'])
            except (ValueError,TypeError): continue
            if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):continue
            writer.writerow(row);kept+=1
    print(f'{kept} of {total} rows retained; {total-kept} excluded. Estimated coordinate columns were not promoted.')
if __name__=='__main__': clean(sys.argv[1],sys.argv[2])
