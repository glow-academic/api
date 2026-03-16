#!/usr/bin/env python3
"""Format table schema data into better markdown."""

from collections import defaultdict


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
    return {"name": table_name, "formatted": f"`{table_name}`({cols_str})"}


def group_tables(tables):
    """Group tables by prefix."""
    groups = defaultdict(list)
    other = []

    for table in tables:
        name = table["name"]
        # Extract prefix (everything before first underscore or whole name)
        if "_" in name:
            prefix = name.split("_")[0]
            groups[prefix].append(table)
        else:
            other.append(table)

    return groups, other


def main():
    """Main function."""
    with open("/tmp/table_data.txt") as f:
        lines = f.readlines()

    tables = []
    for line in lines:
        formatted = format_table_markdown(line)
        if formatted:
            tables.append(formatted)

    # Group tables
    groups, other = group_tables(tables)

    # Build markdown
    output = []
    output.append("# Database Schema - Public Schema")
    output.append("")
    output.append("## Legend")
    output.append("")
    output.append("- **Primary Keys**: <u>underlined</u>")
    output.append("- **Foreign Keys**: *italicized*")
    output.append("- **Regular Columns**: plain text")
    output.append("")
    output.append("---")
    output.append("")

    # Sort groups alphabetically
    sorted_groups = sorted(groups.items())

    # Output grouped tables
    for prefix, group_tables_list in sorted_groups:
        output.append(f"## {prefix.title()} Tables")
        output.append("")
        for table in sorted(group_tables_list, key=lambda x: x["name"]):
            output.append(f"- {table['formatted']}")
        output.append("")

    # Output ungrouped tables
    if other:
        output.append("## Other Tables")
        output.append("")
        for table in sorted(other, key=lambda x: x["name"]):
            output.append(f"- {table['formatted']}")
        output.append("")

    print("\n".join(output))


if __name__ == "__main__":
    main()
