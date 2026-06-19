import csv
from pathlib import Path

import numpy as np

simulation_dir = Path(__file__).resolve().parent / "simulation_results"
output_csv = Path(__file__).resolve().parent / "neutron_flux_results.csv"

# Create or overwrite the CSV file and write headers
with open(output_csv, mode="w", newline="") as csv_file:
    writer = csv.writer(csv_file)
    writer.writerow(["Filename", "Step", "Neutron Flux", "Neutron Flux Change"])

    # Loop through files 0-624 and extract data from npz files
    for i in range(30):
        filename = f"specific_data_{i}.npz"
        filepath = simulation_dir / filename

        if filepath.exists():
            # Load the npz file
            data = np.load(filepath, allow_pickle=True)
            
            # Access the 'data' array in the npz file
            arrays = data['data']
            # sigma_a = arrays[-1]['sigma_a']

            # Find the step 999 entry and extract neutron_flux and neutron_flux_change
            for entry in arrays:
                if entry['step'] == 19999:
                    neutron_flux = entry['neutron_flux']
                    neutron_flux_change = entry['neutron_flux_change'][0]  # Assuming it's a 1-element array
                    writer.writerow([filename, entry['step'], neutron_flux, neutron_flux_change])
                    break  # Exit the loop once step 999 is found

print(f"Data extraction complete. Results saved to {output_csv}.")
