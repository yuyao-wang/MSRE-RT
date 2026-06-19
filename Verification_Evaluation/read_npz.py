import numpy as np
import os
import sys

def read_npz(file_path):
    # Load the .npz file with allow_pickle=True
    data = np.load(file_path, allow_pickle=True)

    # List all the arrays stored in the .npz file
    print("Available arrays in the .npz file:")
    for key in data.files:
        print(f"Array name: {key}, Shape: {data[key].shape}")
        
        # Print the actual data (or a subset, depending on size)
        print(data[key])

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python read_npz.py <folder-path> <npz-file-path>")
    else:
        folder_path = sys.argv[1]
        npz_file = sys.argv[2]

        # Change to the specified directory
        try:
            os.chdir(folder_path)
            print(f"Changed directory to {folder_path}")
        except FileNotFoundError:
            print(f"Error: The folder '{folder_path}' does not exist.")
            sys.exit(1)
        
        # Now read the .npz file
        read_npz(npz_file)
