from settings import OUTPUT_FILE_NAME
import csv

class CsvGeneration:

    def generate_csv_output(self, registers: list[int], headers: list[str]|None):
        with open(OUTPUT_FILE_NAME, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            if headers:
                writer.writerow(headers)
            writer.writerow(registers)