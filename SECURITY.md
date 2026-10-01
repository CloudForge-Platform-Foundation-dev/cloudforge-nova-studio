# Security Policy

## รายงานช่องโหว่

หากพบช่องโหว่ด้านความปลอดภัยใน CloudForge Nova Studio กรุณาอย่าเปิด public issue
ให้ส่งอีเมลมาที่ **niphan1000@gmail.com** พร้อมรายละเอียด:

- ขั้นตอนการ reproduce
- ผลกระทบที่คาดว่าจะเกิด
- เวอร์ชัน/commit ที่พบปัญหา

จะตอบกลับภายใน 5 วันทำการ

## เวอร์ชันที่ยังซัพพอร์ตอยู่

| เวอร์ชัน | ซัพพอร์ต |
|---|---|
| 0.2.x | ✅ |

## ขอบเขตที่เกี่ยวข้อง

Repo นี้เรียกใช้ Anthropic API และ Knowledge Studio API โดยตรง — ห้าม commit API key หรือ
credential ใดๆ ลงใน repo เด็ดขาด ใช้ environment variable เท่านั้น (ดู `.env.example`)
