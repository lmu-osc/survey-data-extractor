import pandas as pd
from config import TRANSLATABLE_COLUMNS

# read in complete Excel file to a pandas dataframe
df = pd.read_excel("data/LMU_wide_survey_DE.xlsx")

# filter the dataframe to only include the translatable columns
df = df[["session_id"] + TRANSLATABLE_COLUMNS]


print(df.head())

# write to a CSV file
df.to_excel("data/LMU_wide_survey_DE_selected.xlsx", index=False)