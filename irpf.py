# global variables
##################
year = 2023
file_name = str(year) + '/cryptos - Tx.csv'
old_coins = ['USD','ETH','USDC','USDT','BNB','SOL','BUSD','TOK','VLX','Deeznuts','METIS','LEAFTY','B20','SPI','PAINT','XED','DDIM','RLY','Minifootball','KISHU','Highrise','ERN','GLMR','LOOKS','YUZU','BTC','SOL','EUR','OVR','XYM','BLOK','EWT','ENJ','KKT','GMS','IOT','DPR','STUD','Cryptoshack','Highrise creature','Osiris cosmic kids','ChubbyKaiju','Bridge over troubled water','POLP','KSM','CRO']

# functions
###########
def read_csv(file_name):

    import csv

    data = list(csv.reader(open(file_name)))

    return data

def clean_data(data):

    # remove header
    data = data[1:]

    # remove active management line
    i = 0
    while data[i][0] != 'active management':
        i = i + 1
    del data[i]

    return data

def remove_end_dates(data):

    from datetime import datetime

    # removes all data after end date
    end = datetime(year, 12, 31)

    iend = len(data) - 1
    while datetime.strptime(data[iend][0], '%d-%m-%Y') > end:
        iend = iend - 1
    data = data[:iend+1]

    return data

def remove_begin_dates(data):

    from datetime import datetime

    begin = datetime(year, 1, 1)

    ibegin = 0
    while datetime.strptime(data[ibegin][0], '%d-%m-%Y') < begin:
        ibegin = ibegin + 1
    data = data[ibegin:]

    return data

def create_sales(data):

    from datetime import datetime

    min_prices, buys, sales, fees, balances = {}, {}, {}, {}, {}
    for idx, row in enumerate(data):

        # define variables for this row
        ticker = row[2]
        amount = float(row[3])

        # if fee is incorrectly listed as a positive amount, change to negative
        if ticker[:3] == 'fee' and amount > 0:
            amount = -amount

        is_price, price = set_price(ticker,amount,min_prices,row)
        wallet = row[8]
        chain = row[9]

        # skip internal transfer rows
        if '-' in wallet or '-' in chain:
            # check that we don't have a transfer with prices.  A transfer with prices directly preceded by a transfer w/o prices would be the corresponding transfer fees & would be valid
            if (row[4] or row[5]) and idx > 0 and data[idx-1][8] != wallet:
                print("We shouldn't have a transfer with sell prices.", row)
                exit()
            continue

        # update min prices in case we don't have a buy price, we use the min price of all time for that token
        if is_price:
            min_prices = update_min_prices(ticker,price,min_prices)

        # update balances
        if ticker[:3] == 'fee':
            bticker = ticker[3:]
        else:
            bticker = ticker
        buy_price, buys, balances = update_balances(idx,bticker,price,amount,min_prices,balances,buys,row)

        # if we have transferred to someone else, then no need to look at sales
        if 'Sent' in row[10]:
            continue

        # only look at rows that are sales and are from the current year
        begin = datetime(year, 1, 1)
        end = datetime(year, 12, 31)
        if amount < 0 and datetime.strptime(row[0], '%d-%m-%Y') >= begin and datetime.strptime(row[0], '%d-%m-%Y') <= end:

            if not is_price:
                price = buy_price

            if ticker[:3] == 'fee':
                # add fee to list of fees
                sales = add_sale(idx,bticker,price,amount,balances,min_prices,row,sales)
                fees = add_fee(ticker,price,amount,balances,min_prices,row,fees)
            else:
                # add sale to list of sales
                sales = add_sale(idx,ticker,price,amount,balances,min_prices,row,sales)


    # if we have a sale at a loss and there are purchases within two months, then we don't compute until they are sold
    sales = reduce_losses(balances,buys,sales)

    # remove indices from sales
    sales_write = {}
    for key in sales:
        if key not in sales_write:
            sales_write[key] = []
        for sale in sales[key]:
            sales_write[key].append(sale[1:])

    # write csv file with gains and fees
    write_output_file(sales_write,fees)

    return sales

def reduce_losses(balances,buys,sales):

    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    # loop through tickers
    original_sales = dict(sales)
    for key in balances:

        balances_key = dict(balances[key])

        # if no remaining balances then no problem!
        if not balances_key or len(balances_key['idx']) == 0:
            continue

        if key in sales:

            sales_key = list(original_sales[key])

            # if no sales then no problem!
            if len(sales_key) == 0:
                continue
        else:
            continue

        buys_key = list(buys[key])

        # if we have no buys then continue
        if not balances_key or not buys_key or len(buys_key) == 0:
            continue

        # take sum of remaining_balance
        total_remaining_balance = sum(balances_key['amounts'])

        # go backwards through buys while we get to the buy before the first one in balances 
        ifirst = balances_key['idx'][0]
        idx = len(buys_key) - 1
        while idx > 0 and buys_key[idx][0] >= ifirst:
            idx = idx - 1

        # go forwards through last_sales
        for isale, sale in enumerate(sales_key):

            # if no remaining balances then no problem!
            if not balances_key or len(balances_key['idx']) == 0:
                break

            # only look at sales after the buy previous to the first remaining balance
            if sale[0] < idx:
                continue

            # if isale is gain, continue
            if sale[6] > 0:
                continue

            # we will subtract from first balance, then continue until the sale amount is satisfied while the date is less than 2 months before
            amount = abs(sale[3])
            current_buy, total_buy = 0, 0
            date = datetime.strptime(balances_key['dates'][0], '%d-%m-%Y')
            while total_buy < amount and date < datetime.strptime(sale[1], '%d-%m-%Y') + relativedelta(months=+2) and len(balances_key['amounts']) > 0:

                if balances_key['idx'][0] < sale[0]:
                    del balances_key['amounts'][0], balances_key['prices'][0], balances_key['idx'][0], balances_key['dates'][0]
                    if len(balances_key['amounts']):
                        date = datetime.strptime(balances_key['dates'][0], '%d-%m-%Y')
                    continue 

                if total_buy + balances_key['amounts'][0] <= amount:
                    print('balances_key  = ',balances_key)
                    current_buy = balances_key['amounts'][0]
                    total_buy = total_buy + current_buy
                    del balances_key['amounts'][0], balances_key['prices'][0], balances_key['idx'][0], balances_key['dates'][0]
                    if len(balances_key['amounts']):
                        date = datetime.strptime(balances_key['dates'][0], '%d-%m-%Y')

                else:
                    print('balances_key  = ',balances_key)
                    current_buy = amount - total_buy
                    total_buy = amount
                    balances_key['amounts'][0] = balances_key['amounts'][0] - current_buy

                # subtract amount from isale
                print('REDUCING SALE!!!!', key )
                print('before', sales[key][isale] )
                sales[key][isale][3] = sales[key][isale][3] - current_buy
                sales[key][isale][6] = -sales[key][isale][3]*(sales[key][isale][4] - sales[key][isale][5])
                print('after', sales[key][isale] )

    return sales

def write_output_file(sales,fees):

    import csv

    outfile = str(year) + '/txCriptos' + str(year) + '.csv'
    with open(outfile, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows([['Ventas'],['Fecha','Token','Cantidad','Precio de compra','Precio de venta','Ganancias']])

    total_gains = 0
    for key in sales:
        for i in sales[key]:
            total_gains = total_gains + i[5]

        with open(outfile, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(sales[key])
#            writer.writerows([[],['Ganancias totales',col_totals[5]]])

    with open(outfile, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerows([[],['Ganancias totales',total_gains]])
        writer.writerows([[],[],['Comisiones'],['Fecha','Token','Cantidad','Precio','Comisiones']])

    total_fees = 0
    for key in fees:
        for i in fees[key]:
            total_fees = total_fees + i[4]
        with open(outfile, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(fees[key])

    with open(outfile, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerows([[],['Comisiones totales',total_fees]])

    return 0

def add_fee(ticker,price,amount,balances,min_prices,row,fees):

    if row[5]:
        sell_price = float(row[5])
    else:
        if row[4]:
            sell_price = float(row[4])*float(row[1])
        else:
            print("Why is there no sale price?",row)
            exit()

    # add new ticker to fees
    if ticker[3:] not in fees:
        fees[ticker[3:]] = []

    fees[ticker[3:]].append([row[0],ticker[3:],-amount,sell_price,-amount*(sell_price)])    
    
    return fees

def add_sale(idx,ticker,price,amount,balances,min_prices,row,sales):

    if row[5]:
        sell_price = float(row[5])
    else:
        if row[4]:
            sell_price = float(row[4])*float(row[1])
        else:
            print("Why is there no sale price?",row)
            exit()

    # add new ticker to sales
    if ticker not in sales:
        sales[ticker] = []

    # don't declare stuff that is very small
    if abs(amount*(price - sell_price)) > 1e-6:
        sales[ticker].append([idx,row[0],ticker,-amount,price,sell_price,amount*(price - sell_price)])    

    return sales

def update_balances(idx,ticker,price,amount,min_prices,balances,buys,row):
    
    # if positive, add to end of list.
    if amount > 0:
        date = row[0]
        balances = increase_balances(ticker,idx,date,price,amount,balances)
        if ticker not in buys:
            buys[ticker] = []
        buys[ticker].append([idx,amount])
    
    # else subtract from first element. 
        # when first element is 0, remove and continue with next
        # if no more elements, continue to next row and set price as min overall price for that ticker
        # sum(price*amount)/total amount
    if amount < 0:
        price, balances = reduce_balances(ticker,amount,min_prices,balances,row)

    return price, buys, balances

def increase_balances(ticker,idx,date,price,amount,balances):
    # add to ticker's dictionary key
    if ticker not in balances:
        balances[ticker] = {}
        balances[ticker]['idx'] = []
        balances[ticker]['dates'] = []
        balances[ticker]['prices'] = []
        balances[ticker]['amounts'] = []

    # if positive, add to end of list.
    if  amount > 0:
        balances[ticker]['idx'].append(idx)
        balances[ticker]['dates'].append(date)
        balances[ticker]['prices'].append(price)
        balances[ticker]['amounts'].append(amount)

    return balances

def reduce_balances(ticker,amount,min_prices,balances,row):
    # keep looping while there is still amount to be subtracted from first elements and while there are still elements
    sum_price = 0 # this is a sum of the prices times the amounts
    remaining_amount = amount # the remaining amount to be subtracted

    # error catching for 0 amounts
    if amount == 0:
        print("Must change the amount for this row.",row)
        exit()

    # if no balance is available for this ticker
    if not balances or ticker not in balances or len(balances[ticker]['amounts']) == 0:
        if ticker in min_prices:
            sum_price = min_prices[ticker]
        if ((ticker[:3] != 'fee' and ticker not in old_coins) or (ticker[:3] == 'fee' and ticker[3:] not in old_coins)) and abs(float(row[3])*float(row[5])) > 0.01:
            print("No balance is available for this row, but we are reducing balance by ",abs(float(row[3])*float(row[5]))," euros",row)
        return sum_price, balances

    # error catching for larger sell amounts than currently available.  The lowest price is used for the missing amounts
    if abs(amount) > sum(balances[ticker]['amounts']):
        min_price = min(balances[ticker]['prices'])
#        min_price = min_prices[ticker]
        idx = balances[ticker]['prices'].index(min_price)
        balances[ticker]['amounts'][idx] = balances[ticker]['amounts'][idx] + abs(amount) - sum(balances[ticker]['amounts'])
        if ((ticker[:3] != 'fee' and ticker not in old_coins) or (ticker[:3] == 'fee' and ticker[3:] not in old_coins)) and abs(max(balances[ticker]['prices'])*(abs(amount) - sum(balances[ticker]['amounts']))) > 0.01:
            print("Sell amount is larger than current balance by ",max(balances[ticker]['prices'])*(abs(amount) - sum(balances[ticker]['amounts']))," euros at max price ",max(balances[ticker]['prices']),row)

    while remaining_amount < 0 and balances[ticker] and len(balances[ticker]['prices']) > 0:
        # if the specified amount is less than the first element in list
        if abs(remaining_amount) < balances[ticker]['amounts'][0]:
            balances[ticker]['amounts'][0] = balances[ticker]['amounts'][0] + remaining_amount
            sum_price = sum_price - remaining_amount*balances[ticker]['prices'][0]
            remaining_amount = 0
        else:
            remaining_amount = remaining_amount + balances[ticker]['amounts'][0]
            sum_price = sum_price + balances[ticker]['amounts'][0]*balances[ticker]['prices'][0]
            del balances[ticker]['amounts'][0], balances[ticker]['prices'][0], balances[ticker]['dates'][0], balances[ticker]['idx'][0]

    return sum_price/-amount, balances

def set_price(ticker,amount,min_prices,row):

    # set buy price depending on conditions
    try:
        price = float(row[7])
        is_price = True
    except:
        is_price = False
        if min_prices and ticker in min_prices:
            price = max(0,min_prices[ticker])
        else:
            price = ''
        if amount > 0 and '-' not in row[8] and '-' not in row[9]:
            print('This data is a purchase but with no buy price in euros. Fix this!!!')
            print(row)
            exit()

    return is_price, price

def update_min_prices(ticker,price,min_prices):
    # update min price for that ticker
    if price and price != -1:
        if ticker not in min_prices:
            min_prices[ticker] = price
        else:
            min_prices[ticker] = min(price,min_prices[ticker])

    return min_prices

# main code
###########
if __name__ == '__main__':

    # read data from csv
    data = read_csv(file_name)

    # clean data
    data = clean_data(data)

    # loop through data and fill in price gaps
#    up_to_data = remove_end_dates(data)
    up_to_data = list(data)

    sales = create_sales(up_to_data)
    