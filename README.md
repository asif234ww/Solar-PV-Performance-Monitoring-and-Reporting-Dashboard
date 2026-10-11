# Solar PV Performance Monitoring and Reporting Dashboard

Python analysis and a Power BI dashboard that monitor the performance of 22 solar inverters at a plant in India. The project validates the sensor data, benchmarks every inverter against the fleet, and finds days when an inverter produced far less than expected.

## Dataset
Kaggle "Solar Power Generation Data" (Plant 1 generation and weather sensor files): 34 days of 15-minute readings from 22 inverters.

## What the project does
1. **Validates the data:** 68,778 inverter readings checked for duplicates, faulty (negative) readings and missing time slots. Result: 0 duplicates, 0 faulty readings, 698 missing time slots.
2. **Benchmarks inverters:** calculates daily yield for each inverter and compares it with the fleet median (7,228 kWh/day). An inverter is flagged as underperforming if its average daily yield is below 90% of the median.
3. **Finds low-output days:** flags any inverter-day below 80% of that day's fleet median.
4. **Reports:** a Power BI dashboard with KPI cards, yield per inverter, total plant generation per day, a table of low-output days, and an inverter slicer.

## Key findings
- The fleet was consistent: no inverter fell below the 90% limit, and the lowest was 9.6% below the median.
- 6 low-output inverter-days across 4 inverters, with an estimated 16,094 kWh of lost output.

## Tools
Python (Pandas, NumPy, Matplotlib), Power BI

## How to run
```
pip install pandas numpy matplotlib
python solar_pv_project.py --gen Plant_1_Generation_Data.csv --weather Plant_1_Weather_Sensor_Data.csv
```
The script creates an `output_solar` folder with CSV tables and charts. Import those CSV files into Power BI Desktop, or open `Solar_PV_Dashboard.pbix`.

## Notes and assumptions
- The 90% and 80% limits were set before running the analysis and were not changed after seeing the results.
- Estimated lost output is the gap between an inverter's yield and that day's fleet median, so it is an estimate and not a measured loss.
- The dataset's DC/AC power columns have a scale mismatch, so inverter efficiency was not used as a finding.

## Files
- `solar_pv_project.py`: analysis script
- `output_solar/`: generated tables and charts
- `Solar_PV_Dashboard.pbix` and `Solar_PV_Dashboard.pdf`: dashboard
