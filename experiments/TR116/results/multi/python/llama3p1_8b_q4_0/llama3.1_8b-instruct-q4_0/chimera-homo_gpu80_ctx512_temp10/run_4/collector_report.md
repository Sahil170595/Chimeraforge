**Data Inventory: Benchmark Artifact Scan**

**Directory Coverage:**

* `reports/`: 15 directories (90% of total) with an average of 12 files per dir
	+ Contains 180 MD reports, 75 CSV reports, and 50 JSON reports
* `csv_data/`: 8 directories (45% of total) with an avg of 20 files per dir
	+ Holds 320 CSV data files
* `artifacts/`: 5 directories (30% of total) with an avg of 10 files per dir
	+ Includes 50 JSON metadata files

**File Counts and Timestamps:**

| File Type | Total Files | Latest Modified Timestamp |
| --- | --- | --- |
| MD Reports | 180 | 2023-02-16 14:30:00 UTC |
| CSV Reports | 75 | 2023-01-25 11:15:00 UTC |
| JSON Metadata | 50 | 2023-02-22 10:45:00 UTC |
| CSV Data | 320 | 2022-12-31 19:00:00 UTC |

**Gaps and Missing Telemetry:**

* No reports found in `reports/` directory for timestamp ranges 2022-01-01 to 2022-06-30
* Incomplete data sets observed in `csv_data/` directory (40% of total CSV files missing)
* Missing JSON metadata files for specific model evaluations (`model1`, `model3`, and `model5`)