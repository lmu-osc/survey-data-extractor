import pandas as pd
from config import TRANSLATABLE_COLUMNS

# read in complete tab separated file to a pandas dataframe
with open("data/LMU_wide_survey_DE.tab", "r") as f:
    df = pd.read_csv(f, sep="\t")
    
# filter the dataframe to only include the translatable columns
df = df[["session_id"] + TRANSLATABLE_COLUMNS]


print(df.head())

# write to a tab delimited file
df.to_csv("data/LMU_wide_survey_DE_selected.tab", sep="\t", index=False)