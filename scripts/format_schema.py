#!/usr/bin/env python3
"""Format table schema data into markdown."""


def format_table_markdown(line):
    """Format a single table line into markdown."""
    parts = line.strip().split("|")
    if len(parts) != 4:
        return None

    table_name = parts[0]
    pk_cols_str = parts[1]
    fk_cols_str = parts[2]
    all_cols_str = parts[3]

    # Parse columns
    pk_cols = set(pk_cols_str.split(", ")) if pk_cols_str else set()
    fk_cols = set(fk_cols_str.split(", ")) if fk_cols_str else set()
    all_cols = [col.strip() for col in all_cols_str.split(", ")] if all_cols_str else []

    # Format columns
    formatted_cols = []
    for col in all_cols:
        if col in pk_cols:
            formatted_cols.append(f"<u>{col}</u>")
        elif col in fk_cols:
            formatted_cols.append(f"*{col}*")
        else:
            formatted_cols.append(col)

    cols_str = ", ".join(formatted_cols)
    return f"{table_name}({cols_str})"


def main():
    """Main function."""
    with open("/tmp/table_data.txt") as f:
        lines = f.readlines()

    formatted_lines = []
    for line in lines:
        formatted = format_table_markdown(line)
        if formatted:
            formatted_lines.append(formatted)

    print("\n".join(formatted_lines))


if __name__ == "__main__":
    main()
