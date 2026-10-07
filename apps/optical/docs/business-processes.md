# Business processes

1. Customer -> Optical Profile is created automatically on first exam/prescription/order.
2. Eye Examination -> "Create > Optical Prescription" (new prescription supersedes the previous Current one and links to it).
3. Optical Order (Draft): choose customer, prescription (defaults to the latest), items with roles
   (Frame / Right Lens / Left Lens / Contact Lens / Coating / Accessory / Service), discount, insurance plan.
4. Confirm Order -> creates the Optical Job and, if there is an insurance portion, an Insurance Claim.
5. Create > Customer Invoice (draft Sales Invoice, stock moves on submit). Payments are ERPNext Payment Entries.
6. Insurance: approve the claim (approval number) -> Create > Insurer Invoice -> payment settles the claim.
7. Optical Job stages (configurable in Optical Settings): New, Prescription Verification, Measurements Confirmed,
   Preparation, Laboratory, Assembly, Quality Control, Ready, Notified, Delivered. Use "Next Stage".
   External lab: Create > Purchase Order from the job; actual return is stamped when the job leaves Laboratory.
8. QC: create from the job. Pass moves the job to Ready. Fail -> Create > Optical Remake.
9. Remake: Requested -> Approved (creates a new urgent job) -> Completed.
10. Delivery: allowed only with a submitted customer invoice and no balance (unless allowed in settings).
    Delivery creates Optical Warranty records for the frame and lenses.
11. Warranty Claim: repair / replacement / remake; approved remake claims create a Remake.
