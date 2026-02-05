from allyin_licensing.license_manager import LicenseManager
fixed_secret = b'Ar_tw-PJgfvxhRj_N5GjaZgGjrwU5cE3WqnBFzKGT-o='
lm = LicenseManager(product_id="Aqeedai")
lm.secret_key = fixed_secret
key, data = lm.generate_license_key(
    customer_id="nirajmac",
    days=7,
    license_type="paid",
    sigtype="hmac"
)

print(f"License Key: {key}")
print(f"License Data: {data}")