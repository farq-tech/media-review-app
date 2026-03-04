# POI Delivery QA Pipeline

Enterprise-grade QA pipeline implementing the **Final POI Delivery QA Specification** for client delivery.

## Outputs

| File | Description |
|------|-------------|
| `POI_Final_Clean.csv` | Deduplicated, validated clean dataset |
| `POI_Duplicates_Removed.csv` | Records merged into golden records |
| `POI_QA_Report.xlsx` | Full QA report with error breakdowns |

## Quick Start

```bash
pip install -r requirements.txt
python poi_qa_pipeline.py
```

## Specification Mapping: Client Feedback → Validation Rules

| Client Feedback | Validation Rule | Automated/Manual |
|-----------------|-----------------|-----------------|
| Duplicate POIs | Deduplication (2 rules trigger) | Automated |
| Business name incorrect | Business identity validation | Automated flag |
| Arabic phonetic mismatch | Name reject patterns | Automated flag |
| Image and text phone mismatch | `FLAG_PHONE_CONFLICT` | Manual (OCR required) |
| Phone scientific notation | Auto-fix `9.66E+11` → `966...` | Automated |
| Completely wrong category | Category mapping + restaurant checks | Automated |
| Commercial license wrong | 10 digits, numeric, unique | Automated |
| Homepage incorrect | Invalid domain blocklist | Automated |
| Interior/exterior mixed | `exterior_url == interior_url` | Automated |
| Duplicate images | Duplicate URL detection | Automated |
| Wrong POI media | Signage vs name match | **Manual** (vision AI) |
| Video unusable | Video content check | **Manual** |
| Menu QR misclassification | QR in image | **Manual** |
| Multiple POIs in image | Mall corridor detection | **Manual** |
| Image quality (blurry/dark) | Resolution check | **Manual** |
| Wrong working hours | Format + open/close logic | Automated |

## Pipeline Steps (Spec §11)

1. **Deduplicate** – Merge duplicates into golden records
2. **Merge** – Golden record = highest completeness; merge fields + media URLs
3. **Validate coordinates** – Saudi Arabia bounds (implicit in dedup)
4. **Validate categories** – Map + restaurant menu/seating check
5. **Validate phones** – Fix scientific notation; flag invalid
6. **Validate working hours** – Format + impossible ranges
7. **Validate licenses** – 10 digits, numeric, unique
8. **Validate media** – Duplicate URLs, exterior=interior conflict
9. **Validate phonetic names** – Reject branch/phone in name
10. **Export** – Clean dataset + QA report

## Deduplication Rules (Spec §1)

Duplicate when **any 2 rules** trigger:

| Rule | Condition |
|------|-----------|
| Name proximity | Same normalized name + distance < 30 m |
| Phone proximity | Same phone + distance < 50 m |
| Fuzzy name | Similarity ≥ 0.90 + same category + distance < 40 m |
| Building match | Same building + floor + entrance |

## Golden Record Merge Fields

- Phone Number  
- Website  
- Working Hours  
- Media URLs  
- Social Media  
- Commercial License  

## Final Delivery Gate (Spec §10)

| Check | Required |
|-------|----------|
| Duplicate POI | 0 |
| License errors | 0 |
| Media conflicts | 0 |
| Accuracy | ≥ 98% |

## Manual Review Items

These require human or vision AI:

- **FLAG_PHONE_CONFLICT** – OCR phone ≠ dataset phone  
- **Wrong POI media** – Image signage doesn't match POI name  
- **Video validation** – Interior vs exterior content  
- **Menu QR** – Image contains QR code  
- **Multiple POIs** – Mall corridor, multiple businesses  
- **Image quality** – Blurry, dark, low resolution  
