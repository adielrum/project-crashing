**Project Crashing in Commercial Construction**

---

**Situation**

A mid-sized commercial office building is currently under construction in a rapidly developing urban district. The project includes structural work, mechanical and electrical installation, interior finishing, inspection, and final handover.

The developer has signed a lease agreement with a major tenant. According to the contract, the building must be delivered by a fixed deadline. If the project is completed late, the developer must pay liquidated damages of Rp 150,000,000 per day. If the project is delivered early, the developer may begin rental operations sooner, generating additional revenue estimated at Rp 100,000,000 per day.

Due to unexpected weather disruptions and supply chain delays, the current projected completion date exceeds the contractual deadline.

The project manager now considers accelerating selected construction activities. Some activities can be shortened by allocating additional crews, increasing overtime, or hiring subcontractors. However, acceleration increases direct costs and may introduce operational risks.

You are part of a consulting team hired to analyze the schedule and propose an acceleration strategy. The team has been given the baseline commercial construction schedule dataset, including:

* List of project activities

* Activity durations

* Precedence relationships

* Resource assignments

* Resource cost rates

* Resource availability limits

Your task is to construct a mathematical model to analyze possible acceleration strategies and provide recommendations.

---

**Model and Analyze**

Develop a mathematical model that captures the trade-offs between project duration and project cost.

Your analysis should include the following components.

**1\. Baseline Modeling**

Using the provided schedule data:

* Represent the project as a network of interdependent activities.

* Compute the baseline completion time and baseline total cost.

---

**2\. Acceleration (Project Crashing)**

Some activities may be shortened by allocating additional resources or increasing work intensity.

For modeling purposes, you may assume:

* Each activity has a minimum feasible duration.

* Reducing duration increases direct cost.

* Acceleration may be continuous or discrete.

* Resource capacity limits must still be respected.

You must clearly state all assumptions you introduce.

Formulate a model that allows:

* Adjustment of activity durations within allowable bounds.

* Cost increases associated with duration reduction.

* Enforcement of precedence constraints.

* Enforcement of resource capacity constraints.

---

**3\. Decision Scenarios**

**Scenario A: Deadline-Driven Optimization**

Determine the minimum additional cost required to complete the project by the contractual deadline.

**Scenario B: Budget-Constrained Optimization**

Given a maximum acceleration budget, determine the minimum achievable completion time.

**Scenario C: Time-Cost Tradeoff Curve**

Construct the **time–cost tradeoff curve** for the project, showing the relationship between:

* Project completion time

* Minimum achievable total cost (plus penalty or minus revenue)

Your analysis should identify:

* The **normal point** (baseline time and cost)

* The **crash point** (minimum feasible time and corresponding cost)

* The pattern of cost increase as project duration decreases

Provide the curve and a brief interpretation of its implications.

---

**4\. Sensitivity and Robustness**

Investigate how sensitive your solution is to:

* Changes in penalty cost per day

* Changes in resource availability

* Changes in maximum crash limits

* Uncertainty in activity duration

Discuss which parameters most strongly influence the recommended strategy.

---

**Share Your Insights**

Your result should:

* Explain your recommended acceleration strategy.

* Identify which activities should be accelerated and why.

* Highlight risks such as resource congestion, safety concerns, or diminishing returns from acceleration.

The goal is to communicate mathematical insights in a form understandable to non-technical decision-makers.

---

**Glossary**

**Activity:** A task required to complete the project.

**Precedence Constraint:** A requirement that one activity must finish before another can begin.

**Project Completion Time:** The finish time of the final activity in the project network.

**Acceleration (Crashing):** The process of reducing activity duration by allocating additional resources or increasing work intensity, typically at increased cost.

**Direct Cost:** Cost directly associated with performing activities.

**Indirect Cost:** Costs dependent on project duration, such as overhead or penalties.

**Resource Capacity:** Maximum available units of a resource at any given time.

---

