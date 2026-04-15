def _float(val, default=0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _recalculate(calc):
    total_hours = calc.printing_time_hours + calc.printing_time_minutes / 60.0

    # Filament cost: from filaments array if present, else from single fields
    filaments = calc.filaments or []
    if filaments:
        fil_total = 0
        for fil in filaments:
            if not isinstance(fil, dict):
                continue
            sw = _float(fil.get('spool_weight'), 0)
            if sw > 0:
                cost = (_float(fil.get('grams_used'), 0) / sw) \
                    * _float(fil.get('spool_price'), 0) \
                    * (1 + calc.markup_percent / 100)
                fil['cost'] = round(cost, 4)
            else:
                fil['cost'] = 0
            fil_total += fil['cost']
        calc.filament_cost = round(fil_total, 4)
    else:
        if calc.spool_weight and calc.spool_weight > 0:
            calc.filament_cost = round(
                (calc.filament_weight_grams / calc.spool_weight)
                * calc.spool_price * (1 + calc.markup_percent / 100), 4)
        else:
            calc.filament_cost = 0

    if calc.electricity_enabled:
        calc.electricity_cost = round(
            (calc.power_consumption / 1000) * total_hours * calc.energy_cost_per_kwh, 4)
    else:
        calc.electricity_cost = 0

    if calc.labor_enabled:
        calc.labor_cost = round(
            (calc.prep_time_minutes / 60 * calc.prep_cost_per_hour)
            + (calc.postprocessing_time_minutes / 60 * calc.postprocessing_cost_per_hour), 4)
    else:
        calc.labor_cost = 0

    if (calc.machine_enabled and calc.machine_return_years
            and calc.machine_return_years > 0
            and calc.machine_daily_hours and calc.machine_daily_hours > 0):
        calc.machine_cost = round(
            (calc.machine_purchase_price * (1 + calc.machine_repair_percent / 100))
            / (calc.machine_return_years * 365 * calc.machine_daily_hours)
            * total_hours, 4)
    else:
        calc.machine_cost = 0

    other_total = sum(item.get('cost', 0) for item in (calc.other_costs or [])
                      if isinstance(item, dict))
    subtotal = (calc.filament_cost + calc.electricity_cost
                + calc.labor_cost + calc.machine_cost + other_total)
    calculated = round(subtotal * (1 + calc.vat_percent / 100), 2)
    if calc.final_price_override is not None and calc.final_price_override > 0:
        calc.total_price = calc.final_price_override
    else:
        calc.total_price = calculated
