import pandas as pd
from config import TRANSLATABLE_COLUMNS

# read in complete tab separated file to a pandas dataframe
with open("data/LMU_wide_survey_DE.tab", "r") as f:
    df = pd.read_csv(f, sep="\t")
    
# filter the dataframe to only include the translatable columns
df = df[TRANSLATABLE_COLUMNS]

# add a row number column to the dataframe
df.insert(0, "row_number", range(1, len(df) + 1))

print(df.head())

# write to a tab delimited file
df.to_csv("data/LMU_wide_survey_DE_selected.tab", sep="\t", index=False)