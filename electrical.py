import argparse
import math
from numbers import Real
import sys
from typing import Dict, List, Sequence, Union


def analyze_dc(
    voltage_v: float,
    resistances_ohm: Union[float, Sequence[float]],
    connection: str = "series",
) -> Dict[str, Union[float, List[float]]]:
    """Analyze a DC source connected to resistors in series or parallel."""
    if isinstance(voltage_v, bool) or not isinstance(voltage_v, Real):
        raise ValueError("Voltage must be a finite number.")
    if not math.isfinite(voltage_v):
        raise ValueError("Voltage must be a finite number.")
    if connection not in ("series", "parallel"):
        raise ValueError("Connection must be 'series' or 'parallel'.")

    is_single_resistor = isinstance(resistances_ohm, Real) and not isinstance(
        resistances_ohm, bool
    )
    if is_single_resistor:
        resistances = [resistances_ohm]
    else:
        if isinstance(resistances_ohm, (str, bytes)):
            raise ValueError("Resistances must be a number or a sequence of numbers.")
        try:
            resistances = list(resistances_ohm)
        except TypeError as exc:
            raise ValueError(
                "Resistances must be a number or a sequence of numbers."
            ) from exc

    if not resistances:
        raise ValueError("At least one resistance is required.")
    for resistance in resistances:
        if (
            isinstance(resistance, bool)
            or not isinstance(resistance, Real)
            or not math.isfinite(resistance)
        ):
            raise ValueError("Every resistance must be a finite number.")
        if resistance == 0:
            raise ValueError("Resistance cannot be zero.")
        if resistance < 0:
            raise ValueError("Every resistance must be greater than zero.")

    if connection == "series":
        equivalent_resistance = sum(resistances)
        current = voltage_v / equivalent_resistance
        branch_currents = [current] * len(resistances)
        branch_voltages = [
            current * resistance for resistance in resistances
        ]
    else:
        equivalent_resistance = 1 / sum(1 / resistance for resistance in resistances)
        branch_voltages = [voltage_v] * len(resistances)
        branch_currents = [
            voltage_v / resistance for resistance in resistances
        ]

    branch_powers = [
        branch_voltage * branch_current
        for branch_voltage, branch_current in zip(branch_voltages, branch_currents)
    ]
    total_current = voltage_v / equivalent_resistance

    if is_single_resistor:
        return {
            "current_a": total_current,
            "power_w": branch_powers[0],
        }

    return {
        "equivalent_resistance_ohm": equivalent_resistance,
        "total_current_a": total_current,
        "branch_currents_a": branch_currents,
        "branch_voltages_v": branch_voltages,
        "branch_powers_w": branch_powers,
        "total_power_w": sum(branch_powers),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate current and power for DC resistor circuits."
    )
    parser.add_argument("voltage", type=float, help="source voltage in volts")
    parser.add_argument(
        "resistances",
        type=float,
        nargs="+",
        help="one or more resistor values in ohms",
    )
    parser.add_argument(
        "--connection",
        choices=("series", "parallel"),
        default="series",
        help="resistor connection type (default: series)",
    )

    try:
        if len(sys.argv) == 1:
            voltage = float(input("Source voltage (V): "))
            resistance_text = input(
                "Resistor values in ohms (separated by spaces or commas): "
            )
            resistances = [
                float(value)
                for value in resistance_text.replace(",", " ").split()
            ]
            connection = input("Connection [series/parallel, default series]: ")
            connection = connection.strip().lower() or "series"
        else:
            args = parser.parse_args()
            if args.voltage is None or not args.resistances:
                parser.error("voltage and at least one resistance are required.")
            voltage = args.voltage
            resistances = args.resistances
            connection = args.connection

        result = analyze_dc(voltage, resistances, connection)
    except (ValueError, EOFError) as exc:
        parser.error(str(exc))

    print(f"Equivalent resistance: {result['equivalent_resistance_ohm']:.6g} ohm")
    print(f"Total current: {result['total_current_a']:.6g} A")
    for index, (current, power) in enumerate(
        zip(result["branch_currents_a"], result["branch_powers_w"]), start=1
    ):
        print(f"R{index}: current={current:.6g} A, power={power:.6g} W")
    print(f"Total power: {result['total_power_w']:.6g} W")


if __name__ == "__main__":
    main()
