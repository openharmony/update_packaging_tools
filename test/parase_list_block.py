def extract_blocks(pkgdiff_command):
    """Extract block ranges from a pkgdiff command."""
    parts = pkgdiff_command.split()
    if len(parts) < 6:
        return []
    parts = pkgdiff_command.replace(',', ' ').split()
    # The block range is in the 6th position (index 5)
    blocks = []
    all_blocks = []
    start = int(parts[6])
    end = int(parts[7])
    # Generate the blocks for the range [start, end)
    blocks.extend(range(start, end))
    print(f'pkg diff len(blocks):{len(blocks)}')
    
    all_blocks.extend(blocks)

    return all_blocks


def extract_blocks_new(new_command):
    """Extract block ranges from a pkgdiff command."""
    parts = new_command.split()
    parts = new_command.replace(',', ' ').split()
    # The block range is in the 6th position (index 5)
    blocks = []
    all_blocks = []
    start = int(parts[2])
    end = int(parts[3])
    # Generate the blocks for the range [start, end)
    blocks.extend(range(start, end))
    print(f'pkg diff len(blocks):{len(blocks)}')
    
    all_blocks.extend(blocks)

    return all_blocks


def read_pkgdiff_file(filename):
    """Read a pkgdiff file and extract blocks from each command."""
    blocks_set = set()
    with open(filename, 'r') as file:
        for line in file:
            line = line.strip()
            if line.startswith("pkgdiff"):  # Only process lines that start with "pkgdiff"
                blocks = extract_blocks(line)
                blocks_set.update(blocks)
            if line.startswith("new"):
                blocks_new = extract_blocks_new(line)
                blocks_set.update(blocks_new)
    return blocks_set


def compare_block_lists(list1, list2):
    """Compare two sets of blocks and print missing blocks in list2."""
    missing_blocks = list1.difference(list2)
    if missing_blocks:
        print("Missing blocks in the second file:")
        for block in sorted(missing_blocks):
            print(block)
    else:
        print("No missing blocks in the second file.")


def main():
    # Replace 'file1.txt' and 'file2.txt' with your actual file names
    file1 = 'system.transfer_1.list'
    file2 = 'system.transfer_2.list'

    # Read and extract blocks from both files
    blocks_file1 = read_pkgdiff_file(file1)
    blocks_file2 = read_pkgdiff_file(file2)

    # Compare the two sets of blocks
    compare_block_lists(blocks_file1, blocks_file2)


if __name__ == "__main__":
    main()