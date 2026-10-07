# Data model

```
Customer (ERPNext) 1-1 Optical Profile
   |-- Eye Examination --> Optical Prescription (previous_prescription chain)
   |-- Optical Order (items: Optical Order Item) --> Sales Invoice (customer share)
   |       |                                     `-> Sales Invoice to insurer (insurer share)
   |       |-- Optical Job (stage_log) --> Optical QC --> Optical Remake
   |       |-- Insurance Claim
   |       `-- Optical Warranty --> Optical Warranty Claim --> Optical Remake
Masters: Optical Laboratory, Insurance Company (+Customer), Insurance Plan, Optical Settings (single)
Item custom fields: Optical Item Type, frame, lens and contact lens attributes
```

Lens modelling: do not create one Item per power. Create Items per product family (design/material/index/coating
via Item Variants or attributes) and put the per-eye power in the prescription; the order row `spec_details`
holds extras such as tint. Contact lens stock uses ERPNext batches (Optical Order Item has Batch No).
