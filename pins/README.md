# `pins/` — เครื่องมือที่ CI ติดตั้ง ถูกตรึงด้วย hash

`pip install ruff` หยิบรุ่นล่าสุด ณ วินาทีที่ job รัน — สอง run ที่ห่างกันหนึ่งชั่วโมง
จึงใช้เครื่องมือคนละตัวได้โดยไม่มีอะไรใน repo เปลี่ยน · และเครื่องมือพวกนี้รันด้วย
สิทธิ์ของ workflow เรา อ่าน source อ่าน token ที่ job นั้นมี

ตรึงด้วย **รุ่นอย่างเดียวไม่พอ** — `--require-hashes` บังคับสองอย่างที่เลขรุ่นไม่ได้
บังคับ: ไฟล์ต้องเป็นไบต์ชุดเดิม **และ dependency ทุกตัวในต้นไม้ต้องถูกระบุไว้**
ล็อกที่ครอบไม่ครบจึงเป็น error ตอนติดตั้ง ไม่ใช่ช่องโหว่ที่เงียบจนถึงวันที่มีคนใช้มัน

| ไดเรกทอรี | ใครใช้ |
|---|---|
| `dev/` | job `lint` และ `test` (ruff · mypy · pytest · pytest-cov · pyyaml) |

## regenerate

```bash
pip install pip-tools
pip-compile --allow-unsafe --generate-hashes --strip-extras \
  --output-file=pins/dev/requirements.txt pins/dev/requirements.in
```

**pin โดยไม่มีใครขยับ = แช่ช่องโหว่ไว้ตลอดกาล** ซึ่งแย่กว่าไม่ pin เลย —
ทุกไดเรกทอรีที่นี่จึงมี Dependabot ดูแลใน `.github/dependabot.yml`
