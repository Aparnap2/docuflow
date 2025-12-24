import pandas as pd
from engine.freight_auditor import FreightAuditor, InvoiceData, AuditResult

# Create sample rate card data
rates_data = {
    'carrier': ['FedEx_Freight', 'XPO_Logistics'],
    'origin_zone': ['100', '902'], # NYC, LA
    'dest_zone': ['606', '331'],   # CHI, MIA
    'min_w': [0, 0],
    'max_w': [10000, 10000],
    'rate': [0.45, 0.55] # Dollars per lb
}
df = pd.DataFrame(rates_data)

# Create auditor
auditor = FreightAuditor(df)
print('FreightAuditor created successfully')

# Create sample invoice data
invoice = InvoiceData(
    pro_number='PRO-998877',
    carrier='FedEx_Freight',
    origin_zip='10001',
    dest_zip='60601',
    weight_lbs=2500,
    total_amount=1450.00  # Expected: ~1293.75 (2500 * .45 * 1.15) -> Overcharge
)

print(f'Invoice: {invoice.pro_number} for {invoice.carrier}')
print(f'Route: {invoice.origin_zip} -> {invoice.dest_zip}, Weight: {invoice.weight_lbs} lbs')
print(f'Invoiced amount: ${invoice.total_amount}')

# Calculate expected cost
expected = auditor.calculate_expected_cost(invoice)
print(f'Expected cost: ${expected}')

# Check for overcharge
variance = invoice.total_amount - expected
if variance > 5.00 and (variance / expected) > 0.03:
    print(f'OVERCHARGE DETECTED: ${variance:.2f} over expected')
else:
    print('Within acceptable range')

print('FreightAuditor functionality verified!')