from openpyxl import Workbook
import time


def main():
    book = Workbook()
    sheet = book.active

    sheet['A1'] = 56
    sheet['A2'] = 43

    now = time.strftime("%x")
    sheet['A3'] = now

    book.save("sample.xlsx")
    
    print("done")


if __name__ == '__main__':
    main()
