# Batch ZIP Upload — Naming Convention

## How It Works

Instead of uploading documents one by one, you can zip all supporting files into a single `.zip` and upload it. The app automatically maps each file to the correct checklist item based on the **filename** (not the extension).

---

## Steps

1. Upload the **Signed Agreement PDF** as usual (reference document)
2. Prepare your supporting files — name each file exactly as shown below
3. Put all files into a single `.zip` archive
4. Click **"Upload ZIP (Batch Check)"**
5. The app runs all checks automatically and fills the results table

---

## File Naming Convention

| Filename (any extension) | Checklist Item | Sno. |
|---|---|---|
| `deposit` | Deposit | 2 |
| `meter_photo` | Meter Photo / Switchboard | 3 |
| `phase_upgrade` | Phase and Upgrade | 4 |
| `roof_pic` | Roof Pic / House Pic | 5 |
| `storey_roof` | Storey and Roof Type | 6 |
| `electricity_bill` | Electricity Bill / NMI | 7 |
| `rate_notice` | Rate Notice | 8 |
| `meter_approval` | Meter Approval | 9 |
| `roof_layout` | Roof Layout Approved | 10 |
| `inverter_location` | Inverter Location Approved | 11 |
| `tilt_frame` | Tilt Frame / Clip Lock | 12 |
| `scissor_lift` | Scissor Lift Required | 13 |
| `welcome_email` | Welcome Email / Invoice / RL / Fact Sheet | 14 |
| `solar_vic` | Solar VIC Loan and Rebate Approved | 15 |
| `finance` | Finance Approved (Brighte/Plenti) | 16 |
| `export_control` | Export Control | 17 |
| `optimizer` | Optimizer | 18 |
| `first_install` | First Time Installation? | 19 |
| `accounts` | Job Checked by Accounts | 20 |
| `customer_informed` | Customer Informed Install Date | 21 |
| `wifi` | Wi-Fi Availability in VIC | 22 |
| `packing_slip` | Packing Slip vs Signed Agreement | 29 |
| `delivery` | Organise Delivery | 30 |
| `raise_wo` | Raise WO for Installer | 31 |
| `inform_installer` | Inform Installer of Install Date | 32 |
| `stc` | Create STC in Green Deal | 33 |
| `cust_name_address` | Customer Name & Address Match | 34i |
| `solar_vic_eligible` | Eligible for Solar VIC Rebate | 34ii |
| `panel_model` | Panel Model # Matches | 35i |
| `inverter_model` | Inverter Model # Matches | 35ii |
| `battery_model` | Battery Model # Matches | 35iii |

---

## Supported File Extensions

Each file can be any of:

- `.pdf`
- `.jpg`
- `.jpeg`
- `.png`

**Examples of valid filenames:**
```
deposit.jpg
meter_photo.png
electricity_bill.pdf
roof_pic.jpeg
panel_model.pdf
```

---

## Rules

- Match is on the **filename stem only** — everything before the first `.`
- Filenames are **case-insensitive** — `Deposit.JPG` and `deposit.jpg` both work
- Files that do **not** match any key are skipped with a warning
- You do **not** need to include all 31 files — only include what you have; unmatched items stay pending
- Do **not** include the signed agreement PDF inside the ZIP — upload that separately first

---

## Example ZIP Structure

```
customer_batch.zip
├── deposit.jpg
├── meter_photo.png
├── phase_upgrade.jpg
├── roof_pic.jpeg
├── storey_roof.jpg
├── electricity_bill.pdf
├── rate_notice.pdf
├── meter_approval.pdf
├── welcome_email.pdf
├── finance.pdf
├── packing_slip.pdf
└── panel_model.pdf
```

---

## Notes

- The batch upload runs checks **sequentially** — a progress bar shows which item is being processed
- Individual item upload still works — you can mix batch and single uploads
- Results are saved automatically after each check, same as manual upload
- If a check fails (OCR error, network issue), it is marked `N/A` with an error remark and the batch continues
