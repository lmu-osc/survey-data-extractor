import pandas as pd


# read in complete tab separated file to a pandas dataframe
with open("data/LMU_wide_survey_DE.tab", "r") as f:
    df = pd.read_csv(f, sep="\t")
    
relevant_columns = [
    "Q6_oa_comment", "Q6_rdm_comment", "Q6_fair_comment", "Q6_code_comment", "Q6_material_comment", "Q6_prereg_comment", "Q6_rr_comment",
    "Q7_oa_comment", "Q7_rdm_comment", "Q7_fair_comment", "Q7_code_comment", "Q7_material_comment", "Q7_prereg_comment", "Q7_rr_comment",
    "Q8_other_1", "Q8_other_2", "Q8_other_3",
    "Q9_other_1", "Q9_other_2", "Q9_other_3",
    "Q10_other_1", "Q10_other_2", "Q10_other_3",
    "Q11_other_1", "Q11_other_2", "Q11_other_3", "Q12_1", "Q12_2", "Q12_3", "Q12_4", "Q12_5"
]

df = df[relevant_columns]

# add a row number column to the dataframe
df.insert(0, "row_number", range(1, len(df) + 1))

print(df.head())

# write to a csv file for inspection
df.to_csv("data/LMU_wide_survey_DE_selected.csv", index=False)