# Stakeholder Guide: Translating Math into Real-World Metrics

Our advanced project models use two parameters, **$\alpha$ (Alpha)** and **$\beta$ (Beta)**, to accurately simulate the diminishing returns of crashing a project. 

In simple terms:
*   **Alpha ($\alpha$)** measures **Overcrowding Inefficiency**. When you cram too many workers into a tight space, they get in each other's way.
*   **Beta ($\beta$)** measures **Overtime Fatigue**. When you force workers to do 12-hour or 14-hour shifts, they get tired and their hourly output drops.

Stakeholders do not need to understand the underlying Cobb-Douglas equations. Instead, you can determine your project's ideal $\alpha$ and $\beta$ by asking your site managers two simple, real-world questions.

---

## 1. Determining Alpha ($\alpha$)

**The Question to Ask:** *"If we normally use 10 guys for this task, and I give you 20 guys (double the workforce), how much faster will the task actually finish?"*

![Alpha Calibration](/Users/macintoshhd/Documents/Adiel/pemod/Pemod-3.0/project-crashing/outputs/sensitivity_analysis/calibration_alpha.png)

If there is zero coordination loss, doubling the workers means you get exactly +100% more daily output (the red dotted line at $\alpha = 1.0$). However, in construction, adding bodies usually results in a traffic jam.

### Alpha Calibration Lookup Table (Double the Workforce)
| If you double your workforce (2x workers), and the task finishes in... | Then your Alpha ($\alpha$) is approximately... | Example Trade |
|---|---|---|
| 50% of original time (Perfect efficiency) | **1.0** | Trench digging, basic manual labor |
| 60% of original time | **0.7 - 0.8** | Bricklaying, standard framing |
| 70% of original time | **0.5** | Electrical wiring, plumbing |
| 85% of original time (Terrible efficiency) | **0.2 - 0.3** | Highly confined spaces, elevator shaft install |

---

## 2. Determining Beta ($\beta$)

**The Question to Ask:** *"If we switch from a standard 8-hour shift to a 12-hour shift (a 50% increase in hours), how much extra work will actually get done in a day?"*

![Beta Calibration](/Users/macintoshhd/Documents/Adiel/pemod/Pemod-3.0/project-crashing/outputs/sensitivity_analysis/calibration_beta.png)

If workers never got tired, a 50% increase in hours would yield a 50% increase in output (the teal dotted line at $\beta = 1.0$). In reality, hours 9 through 12 are less productive than hours 1 through 4.

### Beta Calibration Lookup Table (12-Hour Shifts vs 8-Hour)
| If you switch to 12-hour shifts (+50% hours), and daily output increases by... | Then your Beta ($\beta$) is approximately... | Example Trade |
|---|---|---|
| 50% (Perfect efficiency, no fatigue) | **1.0** | Automated machine operation |
| 35% | **0.7 - 0.8** | Painting, light assembly |
| 20% | **0.4 - 0.5** | Heavy lifting, concrete pouring |
| <10% (Extreme fatigue, almost useless) | **0.2** | Extreme physical labor under high heat |

---

## How to use this for your project
You do not need to choose a single $\alpha$ and $\beta$ for the entire project. The model allows you to assign these values on a **per-task** basis. 

**Action Item:** 
1. Sit down with your subcontractors.
2. Go through the critical path activities.
3. Use the lookup tables above to assign a realistic $\alpha$ and $\beta$ to each major task based on their real-world experience, rather than guessing mathematical exponents.
