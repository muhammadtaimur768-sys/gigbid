import statsmodels.formula.api as smf

fit = smf.ols('revenue ~ price + promo + C(region)', data=df).fit()
print(fit.summary())
