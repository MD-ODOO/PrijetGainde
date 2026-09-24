# -*- coding: utf-8 -*-
"""Pure calculation engine for the net salary simulator."""
from math import floor

TRANSPORT_AMOUNT = 26000.0
IPRES_RG_RATE = 0.056
IPRES_RG_CEILING = 432000.0
IPRES_RC_RATE = 0.024

TRIMF_ANNUAL_TARIFFS = (
    (599999.0, 900.0),
    (999999.0, 3600.0),
    (1999999.0, 4800.0),
    (6999999.0, 12000.0),
    (11999999.0, 18000.0),
    (10**18, 36000.0),
)

IR_TRANCHES = (
    (630001, 1500000, 630001, 0.20, 0),
    (1500000, 4000000, 1500000, 0.30, 174000),
    (4000001, 8000000, 4000001, 0.35, 750000 + 174000),
    (8000001, 13500000, 8000000, 0.37, 1400000 + 750000 + 174000),
    (13500001, 50000000, 13500001, 0.40, 2035000 + 1400000 + 750000 + 174000),
    (50000001, 10**12, 50000001, 0.43, 14600000 + 2035000 + 1400000 + 750000 + 174000),
)

IR_REDUCTIONS = {
    1.5: (0.10, 100000, 300000),
    2.0: (0.15, 200000, 650000),
    2.5: (0.20, 300000, 1100000),
    3.0: (0.25, 400000, 1650000),
    3.5: (0.30, 500000, 2030000),
    4.0: (0.35, 600000, 2490000),
    4.5: (0.40, 700000, 2755000),
    5.0: (0.45, 800000, 3180000),
}

def normalize_part(value):
    value = max(float(value or 1.0), 1.0)
    return round(value * 2.0) / 2.0

def compute_family_parts(marital, children_count, spouse_has_income):
    children_count = max(int(children_count or 0), 0)
    spouse_has_income = bool(spouse_has_income)

    part_ir = 1.0
    if marital == 'married':
        part_ir += 0.5
        if not spouse_has_income:
            part_ir += 0.5
    part_ir += 0.5 * children_count
    part_ir = min(normalize_part(part_ir), 5.0)

    trimf_persons = 1.0
    if marital == 'married' and not spouse_has_income:
        trimf_persons += 1.0
    return part_ir, trimf_persons

def compute_ir(gross):
    gross = max(float(gross or 0.0), 0.0)
    brut = floor(gross / 1000.0) * 1000.0
    annual_gross = brut * 12.0
    abatement = min(0.30 * annual_gross, 900000.0)
    annual_gross_fiscal = annual_gross - abatement

    irrp_before_reduction = 0.0
    for min_check, max_check, base, rate, additive in IR_TRANCHES:
        if min_check <= annual_gross_fiscal <= max_check:
            irrp_before_reduction = (annual_gross_fiscal - base) * rate + additive
            break

    return irrp_before_reduction / 12.0 if irrp_before_reduction > 0 else 0.0, {
        'rounded_gross': brut,
        'annual_gross': annual_gross,
        'abatement': abatement,
        'annual_gross_fiscal': annual_gross_fiscal,
        'ir_before_reduction': irrp_before_reduction,
    }

def compute_ir_from_parts(gross, part_ir):
    ir_before_monthly, details = compute_ir(gross)
    annual_before = details['ir_before_reduction']
    part_ir = normalize_part(part_ir)
    reduction = 0.0

    if part_ir in IR_REDUCTIONS:
        rate_pct, min_red, max_red = IR_REDUCTIONS[part_ir]
        calc = rate_pct * annual_before
        if calc < min_red:
            reduction = float(min_red)
        elif calc > max_red:
            reduction = float(max_red)
        else:
            reduction = calc

    result = max((annual_before - reduction) / 12.0, 0.0)
    details.update({
        'part_ir': part_ir,
        'ir_reduction': reduction,
        'ir_monthly_before_reduction': ir_before_monthly,
    })
    return result, details

def compute_trimf(gross, trimf_persons):
    gross = max(float(gross or 0.0), 0.0)
    persons = max(float(trimf_persons or 1.0), 1.0)
    annual_gross = gross * 12.0

    for max_gross, annual_per_person in TRIMF_ANNUAL_TARIFFS:
        if annual_gross <= max_gross:
            return (annual_per_person * persons) / 12.0
    return 0.0

def compute_ipres(gross, status):
    gross = max(float(gross or 0.0), 0.0)
    rg_base = min(gross, IPRES_RG_CEILING)
    ipres_rg = rg_base * IPRES_RG_RATE
    ipres_rc = gross * IPRES_RC_RATE if status == 'cadre' else 0.0
    return ipres_rg, ipres_rc

def compute_salary(gross, part_ir, trimf_persons, status):
    ir, ir_details = compute_ir_from_parts(gross, part_ir)
    trimf = compute_trimf(gross, trimf_persons)
    ipres_rg, ipres_rc = compute_ipres(gross, status)
    net_before_transport = gross - ir - trimf - ipres_rg - ipres_rc
    return {
        'gross': gross,
        'ir': ir,
        'trimf': trimf,
        'ipres_rg': ipres_rg,
        'ipres_rc': ipres_rc,
        'transport': TRANSPORT_AMOUNT,
        'net_before_transport': net_before_transport,
        'net_to_pay': net_before_transport + TRANSPORT_AMOUNT,
        'ir_details': ir_details,
    }

def solve_gross_for_net(target_net, base_salary, part_ir, trimf_persons, status):
    target_net = max(float(target_net or 0.0), 0.0)
    base_salary = max(float(base_salary or 0.0), 0.0)
    lower = base_salary
    target_without_transport = max(target_net - TRANSPORT_AMOUNT, 0.0)

    high = max(lower, target_without_transport, 100000.0)
    high = max(high * 1.50, lower + 100000.0)

    for _ in range(24):
        result_high = compute_salary(high, part_ir, trimf_persons, status)
        if result_high['net_before_transport'] >= target_without_transport:
            break
        high *= 2.0

    for _ in range(80):
        if high - lower <= 1.0:
            break
        middle = floor((lower + high) / 2.0)
        result_middle = compute_salary(middle, part_ir, trimf_persons, status)
        if result_middle['net_before_transport'] < target_without_transport:
            lower = middle + 1.0
        else:
            high = middle

    center = int(round(high))
    candidates = range(max(int(base_salary), center - 5000), center + 5001)
    best = None
    for gross in candidates:
        result = compute_salary(gross, part_ir, trimf_persons, status)
        diff = abs(result['net_to_pay'] - target_net)
        key = (diff, gross)
        if best is None or key < best[0]:
            best = (key, result)
    return best[1]
