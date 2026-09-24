# Customer Segmentation Case Study

## Objective and data

The goal is to describe useful customer groups in a subscription-service dataset without a target label. The supplied data has 100,200 rows and 14 columns. It contains 200 exact duplicate rows and 200 duplicate IDs; removing exact duplicates leaves 100,000 unique customers. There is no label that would support churn or causal claims.

## Data audit

All original columns, their use, and missingness decisions are summarized below. Date parsing found no invalid values, no login before signup, and no login after the fixed reference date of 2026-06-01. Basic range checks found no ages outside 0-120, negative charges, negative support-call counts, or credit scores outside 300-900. IQR flags were reviewed, not automatically removed: 75 monthly-charge values, 382 total-charge values, 2,719 support-call values, and 147 credit scores fell outside 1.5×IQR fences. These are plausible long tails for spending, service contacts, and scoring; no additional rows were discarded.

| Column | Missing | Use and treatment | Segmentation role |
|---|---:|---|---|
| `customer_id` | 0% | Keep for identifying output rows; exclude from model because it is an identifier. | Not a feature |
| `age` | 0% | Standardize as a numeric feature. | Used |
| `gender` | 0% | EDA only; excluded so clusters focus on commercial and behavioral differences. | Not used |
| `signup_date` | 0% | Parse as date; derive tenure from signup to last login. | Derived feature |
| `last_login_date` | 0% | Parse as date; derive recency relative to 2026-06-01. | Derived feature |
| `contract_type` | 0% | One-hot encode. | Used |
| `internet_service` | 0% | One-hot encode. | Used |
| `payment_method` | 0% | One-hot encode. | Used |
| `monthly_charges` | 0% | Standardize as a numeric feature. | Used |
| `total_charges` | 2.97% | Impute missing values as `monthly_charges × max(tenure_days / 30.44, 1)`; this is an explicit approximation because the observed value is cumulative. | Used after imputation |
| `num_support_calls` | 0% | Standardize as a numeric behavior feature. | Used |
| `credit_score` | 59.95% | Exclude rather than impute a mostly missing bureau field into customer distances. | Not used |
| `referral_code` | 20.29% | Exclude: 79,701 unique values make it high-cardinality and campaign-identifying, rather than a stable segment feature. | Not used |
| `plan_details` | 0% | Treat as structured text; parse plan tier and Mbps, then drop raw string. Parsed plan price matches monthly charges and is not duplicated. | Derived features |

The main categorical distributions are: gender Female 47.99%, Male 47.97%, Other 4.04%; contract Month-to-month 46.81%, One year 27.69%, Two year 25.50%; internet Fiber optic 44.94%, DSL 35.13%, No service 19.94%; payment methods are close to evenly distributed (24.85%-25.11%). `plan_details` has 67,756 distinct raw strings and is not used as free text. `monthly_charges` and `total_charges` have correlation 0.79, reflecting that cumulative spend relates to current recurring charges; both are retained because they describe different commercial aspects. Other numeric correlations are reported in the notebook.

## Feature engineering and preprocessing

The workflow creates `tenure_days`, `recency_days`, `plan_tier`, `speed_mbps`, and `total_charges_filled`. A fixed reference date avoids recency changing between training and prediction. Numeric features are median-imputed and standardized; categorical features are mode-imputed and one-hot encoded. Unknown future categories are ignored by the fitted encoder. Identifier, demographic, campaign, and raw-text fields are not fed to the model.

## Cluster selection and method

K-Means is used after standardization and one-hot encoding. Selection metrics use the same seeded, fixed 12,000-customer sample for k=2 through k=8.

| k | Silhouette | Calinski-Harabasz | Davies-Bouldin |
|---:|---:|---:|---:|
| 2 | 0.219 | 3450.2 | 1.620 |
| 3 | **0.234** | 3092.6 | 1.666 |
| 4 | 0.158 | 2552.8 | 2.103 |
| 5 | 0.150 | 2195.4 | 1.951 |
| 6 | 0.128 | 1941.2 | 2.152 |
| 7 | 0.118 | 1757.0 | 2.079 |
| 8 | 0.113 | 1597.3 | 2.137 |

k=3 has the highest silhouette and a readable profile, but k=2 is better on both Calinski-Harabasz and Davies-Bouldin. Three clusters are selected as a practical descriptive tradeoff that retains the distinct low-activity group while separating lower-spend/shorter-tenure customers from higher-spend/longer-tenure customers. K-Means assumes compact groups in the transformed space, so the three segments are a useful summary rather than a claim that the population has exactly three natural classes.

## Segment profiles

Counts below cover all 100,000 deduplicated customers. Numeric columns show means and medians. Contract and plan summaries give within-segment shares.

| Segment | Customers (%) | Monthly charges mean / median | Tenure days mean / median | Recency days mean / median | Support calls mean / median | Contract mix | Plan mix |
|---|---:|---:|---:|---:|---:|---|---|
| Active Standard-Market Customers | 53,614 (53.61%) | 55.14 / 55.49 | 414 / 264 | 20 / 18 | 1.54 / 1 | 65.9% month-to-month | 50.4% Standard |
| High-Value Long-Term Customers | 29,303 (29.30%) | 94.68 / 94.54 | 1,474 / 1,469 | 11 / 10 | 0.64 / 0 | 57.7% two-year | 50.3% Premium, 47.3% Ultra |
| Dormant / Low-Recent-Activity Customers | 17,083 (17.08%) | 54.98 / 54.85 | 1,021 / 1,031 | 238 / 241 | 3.40 / 3 | 45.9% month-to-month | 49.7% Basic, 49.6% Standard |

The active standard-market group combines lower monthly charges, shorter tenure, and recent logins. The high-value long-term group has higher recurring charges, long tenure, fewer support calls, and a high two-year-contract share. The dormant / low-recent-activity group has much older logins and more support contacts, while its charge level is similar to the active segment. These are descriptive patterns only. Internet-service and payment-method mixes are very similar across clusters and do not explain much of their separation.

## Reproducibility and artifact

The executed notebook records EDA, k-selection scores, profiles, plots, and artifact creation. Install `task1/requirements.txt`, open `customer_segmentation.ipynb` from the `task1` directory, and run all cells. The complete `segment_model.joblib` contains fitted preprocessing, K-Means, cluster names, and a fixed reference date. `predict_segment.py` accepts a new-customer CSV in the original schema and writes segment IDs and names. A separate check loaded the artifact and assigned three synthetic new rows successfully.

## Limitations

Missing cumulative charges are estimated, K-Means geometry depends on feature scaling and encoding, and cluster names encode human interpretation. The solution is not a churn model, does not use the high-missingness credit score, and has not been validated for temporal stability or on future production data.
