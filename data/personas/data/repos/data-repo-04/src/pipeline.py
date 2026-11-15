import pandas as pd

df = pd.read_csv('orders.csv', parse_dates=['date'])
pivot = df.pivot_table(index='region', columns='month', values='revenue', aggfunc='sum')


import statsmodels.formula.api as smf

fit = smf.ols('revenue ~ price + promo + C(region)', data=df).fit()
print(fit.summary())


import openpyxl

wb = openpyxl.load_workbook('model.xlsx')
ws = wb['Assumptions']
