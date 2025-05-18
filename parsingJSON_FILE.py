import json
import os
import pandas as pd
from tqdm import tqdm

# Print current working directory to debug path issues
print(f"Current working directory: {os.getcwd()}")


def parse_json_file(file_path, output_dir="parsed_data", max_rows=None):
    """
    Parse a large JSON file containing crawled data and extract title, URL, and body.

    Args:
        file_path (str): Path to the JSON file
        output_dir (str): Directory to save the output files
        max_rows (int, optional): Maximum number of rows to process (for testing)

    Returns:
        DataFrame: The extracted data
    """

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Initialize empty lists to store data
    titles = []
    urls = []
    bodies = []

    print(f"Reading JSON file: {file_path}")

    try:
        # Load the entire JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Determine if data is a list or a dictionary with a key containing the list
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Find the key that contains the list of pages
            # This assumes there's a key in the dictionary that contains a list of pages
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    items = value
                    break
            else:
                # If no list is found, try to process the dictionary itself
                items = [data]
        else:
            raise ValueError("Unexpected JSON structure. Expected list or dictionary.")

        print(f"Found {len(items)} items to process")

        # Limit the number of items if max_rows is specified
        if max_rows:
            items = items[:max_rows]

        # Process each item in the JSON
        for item in tqdm(items, desc="Processing"):
            # Extract title, URL, and body (adjust these keys based on your JSON structure)
            title = item.get('title', '')
            url = item.get('url', '')
            body = item.get('body', '')

            # Some JSONs might use different keys, try alternatives
            if not title:
                title = item.get('page_title', '')
            if not url:
                url = item.get('page_url', '') or item.get('link', '')
            if not body:
                body = item.get('content', '') or item.get('text', '')

            # Append to lists
            titles.append(title)
            urls.append(url)
            bodies.append(body)

        # Create DataFrame
        df = pd.DataFrame({
            'title': titles,
            'url': urls,
            'body': bodies
        })

        # Save to CSV
        csv_path = os.path.join(output_dir, 'parsed_data.csv')
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"Data saved to {csv_path}")

        # Save to Excel (limited to 1M rows)
        if len(df) <= 1000000:
            excel_path = os.path.join(output_dir, 'parsed_data.xlsx')
            df.to_excel(excel_path, index=False)
            print(f"Data saved to {excel_path}")
        else:
            print("Data too large for Excel output. Only CSV file created.")

        return df

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        # Try to parse the file line by line (for newline-delimited JSON)
        try:
            titles = []
            urls = []
            bodies = []

            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(tqdm(f, desc="Processing lines")):
                    if max_rows and i >= max_rows:
                        break

                    try:
                        item = json.loads(line)
                        title = item.get('title', '')
                        url = item.get('url', '')
                        body = item.get('body', '')

                        # Try alternative keys
                        if not title:
                            title = item.get('page_title', '')
                        if not url:
                            url = item.get('page_url', '') or item.get('link', '')
                        if not body:
                            body = item.get('content', '') or item.get('text', '')

                        titles.append(title)
                        urls.append(url)
                        bodies.append(body)
                    except json.JSONDecodeError:
                        continue

            df = pd.DataFrame({
                'title': titles,
                'url': urls,
                'body': bodies
            })

            csv_path = os.path.join(output_dir, 'parsed_data.csv')
            df.to_csv(csv_path, index=False, encoding='utf-8')
            print(f"Data saved to {csv_path}")

            return df

        except Exception as e:
            print(f"Failed to parse file line by line: {e}")
            raise

    except Exception as e:
        print(f"Error processing file: {e}")
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse a JSON file containing crawled data")
    parser.add_argument("file_path", help="Path to the JSON file")
    parser.add_argument("--output_dir", default="parsed_data", help="Directory to save output files")
    parser.add_argument("--max_rows", type=int, help="Maximum number of rows to process (for testing)")

    args = parser.parse_args()

    # Print directory contents to debug
    print("Files in current directory:")
    for file in os.listdir():
        print(f" - {file}")

    # Print the requested file path
    print(f"Attempting to open: {args.file_path}")

    # Check if file exists
    if os.path.exists(args.file_path):
        print(f"File exists according to os.path.exists")
    else:
        print(f"File does NOT exist according to os.path.exists")

    parse_json_file(args.file_path, args.output_dir, args.max_rows)