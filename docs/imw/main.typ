#import "@preview/arkheion:0.1.2": arkheion, arkheion-appendices
#import "@preview/cetz:0.5.2"
#import "template.typ": *

#let sans(content) = text(font: "New Computer Modern Sans", content)
#let noindent = h(-1.5em)

#set par(first-line-indent: (amount: 2em, all: true))
#show math.equation: set block(breakable: true)
#show figure: set figure.caption(position: top)

#set math.equation(numbering: none)
#show: body => context {
  let labels = query(math.equation.where(block: true))
    .filter(eq => eq.has("label"))
    .map(eq => eq.label)
    .dedup()
  if labels.len() > 0 {
    show selector.or(..labels): set math.equation(numbering: "(1)")
    body
  } else {
    body
  }
}

#let nonumeq = math.equation.with(block: true, numbering: none)
#let dm(x) = box[#nonumeq[#x]]
#let dfrac(x,y) = math.frac(dm(x),dm(y))

#show: article.with(
  title: [*A Cobb–Douglas Approach to \ Resource--Constrained Time–Cost Tradeoff \ Problems in Project Crashing*],
  
  authors: (
    (name: "Timothy Niels Ruslim", affil: "1"),
    (name: "Adiel Rum", affil: "1"),
    (name: "Aisyah Eka Ramadhani", affil: "1"),
    (name: "Faris Hafizhan Hakim", affil: "1"),
    (name: "Raniyah Mutiara Tsani", affil: "1"),
    (name: "Hajwalid Hisyamufid", affil: "1"),
  ),
  
  affiliations: (
    (
      id: "1", 
      dept: "Faculty of Mathematics and Natural Science, Institut Teknologi Bandung, Indonesia", // Industrial and Financial Mathematics Research Division 
    ),
  ),
  
  abstract: [
    Project crashing is a project management technique involving the compression of project schedules to meet deadline requirements, mathematically modelled as a _Resource--Constrained Time--Cost Tradeoff Problem_ (#sans("RC-TCTP")). Often, #sans("TCTP")s operate under the idealistic assumption that crash costs are predetermined. This paper explores optimization models that relax this assumption. In particular, we develop a novel resource--based model that implicitly calculates costs through the _Cobb--Douglas production function_ based on labor overtime and overmanning. While our original non--linear continuous formulation utilized _genetic algorithms_ (GA), we also introduce two simplifications: a discretized mode--based version employing _mixed--integer linear programming_ (MILP) as well as a linearized time--based version that exploited the Cobb--Douglas objective to estimate a crash slope. Both variants are solved with modern _constrained programming_ (CP--SAT) techniques, which proved greater computational tractability without compromising on solution quality. Sensitivity analysis on a real dataset also demonstrated the robustness of these various novel Cobb--Douglas approaches, highlighting its ability to balance efficiency and realism. 
  ],
  
  keywords: (
    "Resource--Constrained Project Scheduling Problem (RCPSP)",
    "Time--Cost Tradeoff Problem (TCTP)",
    "Cobb--Douglas Production Function",
    "Genetic Algorithm (GA)",
    "Mixed--Integer Linear Programming (MILP)",
    "Constraint Programming (CP--SAT)",
    "Project Crashing",
  ),
)

// #pagebreak()

= Introduction

Project management has been a popular area of study in operations research. Aspects of management in facility construction such as contracts, human resources, money, material resources, and uncertainty greatly benefit from a precise mathematical model @demarco2018. In particular, operation research often focuses on optimization models and methods regarding _project scheduling_, which has often become synonymous with project management in operations research @tavares2002 @williams2003. Project scheduling models are diverse, encompassing problems of project feasibility, planning, monitoring, and control. The undeniably most popular such model is packaged in a class of models called _resource--constrained project scheduling problems_ (#sans("RCPSP")s), which focus on the development and prediction of optimal schedules under resource and precedence limitations. See Section 1.1 for a more in--depth explanation. 

In this paper, we focus on a specific subset of project scheduling known as _project crashing_. Project crashing is a "project schedule compression technique" often employed to meet late deadlines due to sudden unexpected complications @caglayan2024. While traditional project crashing might only prioritize the minimization of project completion, the unfortunate context of project crashing also makes it an economic problem, questioning the impact of overblown project costs. Due to the required tradeoff between time and cost, operations research requires more complex models @kim2012. The subclass of #sans("RCPSP")s most suitable for project crashing are the _resource--constrained time--cost tradeoff problems_ (#sans("TCTP")s). See Section 1.3 for greater detail. 

== Resource-Constrained Project Scheduling Problems

Resource-constrained project scheduling problems (#sans("RCPSP")s) are a _class_ of optimization problems for finding optimal schedules for an activities list under two integral constraints: resource limitations and dependency relations. Hence, it is the de-facto standard mathematical model for real--world scheduling matters in literature, especially project scheduling. 

We detail a formalization of #sans("RCPSP")s adapted from that of Artigues et al. @Artigues2008, @Artigues2026 as well as Hartmann and Briskorn @Hartmann2010, @Hartmann2022 as follows. A _project_ is a graph network $(I,cal(E))$ of activity indices $I$ and dependency relations $cal(E)$ between activities. Here, an arc $(i,j) in E$ is a precedence relation between the predecessor $i$ and successor $j$. On the other hand, a _resource set_ is a set $cal(K)$ of resource indices, which may represent renewable or non-renewable resources, equipped with an assignment $R_k >= 0$ of constant per-time available resource. To this, a _resource requirement_ associates to each activity index $i$ and resource index $k$ a constant value $r_(i,k) >= 0$, which intuitively represents how much of resource $k$ activity $i$ requires. 

Furthermore, a _schedule_ is an assignment of project start times $s_i >= 0$ and completion times $e_i >= 0$ to each activity index $i$. In particular, we consider only _feasible_ schedules that satisfy both the dependency relation $cal(E)$ (which typically translates to simple finish-to-start relations) and resource constraints (for examples, the form $sum_i r_(i,k) <= R_k$ at each time step $t$ is common in continuous formulations). Often, fictitious assignments, like $s_0$ and $s_(n+1)$ of start times for instance, are done to represent global project start and completion times. Hence, an #sans("RCPSP") is the problem of finding a feasible schedule that minimizes some _project objective_ $cal(G)(s_(n+1))$. 

== Problem Classifications

To understand the taxonomy of #sans("RCPSP")s, Brucker et al. @Brucker1999 introduced the $alpha | beta | gamma$ notation scheme to create a generalized classification of #sans("RCPSP")s. Here, $alpha$ represents the _resource environment_ which specifies the resource details of the project, which may include renewable resources (such as labor, machinery, etc.) or non-renewable resources (such as raw materials, budget, etc.). Then, $beta$ denotes _activity characteristics_ which detail the dependency relation $cal(E)$ as simply being finish-to-start precedence relations (denoted #sans("prec")), containing time lags (denoted #sans("temp")), or otherwise. Finally, $gamma$ specifies the _objective function_, the measure for an optimal schedule. Classically, this is makespan minimization (purely completion time), but recent formulations have tended towards time-cost tradeoffs (see Section 1.3).

Despite its shortcomings as a pure classification scheme @Herroelen2001, Brucker's notation correctly highlights the three main constituents of an #sans("RCPSP"). In fact, diversity in the choice of resource constraints ($alpha$), temporal constraints ($beta$), and objective functions ($gamma$) becomes the differentiating features between #sans("RCPSP") models. For an extensive survey on the various #sans("RCPSP") models, based on those three components, that have been developed throughout literature over the past 50 years, we refer the readers to @Artigues2026 and @Hartmann2022. 

Now, one often defines the objective $gamma$ from the choice of _decision variables_. In particular, though the project start time (or something similar to it) is always a decision variable, #sans("RCPSP")s also have a representor of activity execution as a primary decision. In light of this, we focus on three pertinent approaches to the decision variables: time--based, mode--based, and resource--based. Time--based decisions are classical for #sans("RCPSP")s, where decision variables directly control the activity schedule. Examples include continuous duration, binary indicators for activity execution, discrete completion times, and more @Hartmann2022. In fact, the first formalization of #sans("RCPSP") by Kelley in 1961 @kelley1961 adopted this approach, utilizing activity decisions and a linear objective. Though a time--based objective is intuitive, it assumes a predetermined crash cost, which may be unrealistic depending on circumstances. 

Next, one has mode--based decisions, which correspond to _multi-mode_ resource--constrained project scheduling problems, denoted #sans("MRCPSP")s. Here, the decision variables are binary selectors of alternative options called "modes" through which activity execution can be implemented @Brucker1999. This approach seems to be preferred in modern literature @Hosseinpour2023, likely due to its computational appeal (see Section 1.4) and flexibility. 

Finally, resource--based decision variables directly determine the resource allotments that affect activity execution, such as binary assignments of workers or dynamic continuous allocations of resources. Problems of this sort are sometimes referred to as _resource investment problems_ (#sans("RIP")s) or traditionally as _resource availability cost problems_ (#sans("RACP")s) @Hartmann2022 @Artigues2026. Unlike problems using time--based objectives, #sans("RIP")s do not assume known crash costs. However, they are generally more computationally tasking. We remark that the choice of decision variables determines the project objective $gamma$, and is thus one of the most important aspects of #sans("RCPSP")s.  

== Time--Cost Tradeoff Problems

Classical #sans("RCPSP")s simply minimize makespan as their objective @Brucker1999. However, as the issue of project crashing glaringly points out, more modern applications often demand consideration of project _costs_ as well. _Resource--constrained time--cost tradeoff problems_ (#sans("RC-TCTP")s) are a class of #sans("RCPSP")s that reduce project costs while minimizing makespan. In general #sans("TCTP")s, regardless of resource--constraints, one often deals with both _direct costs_, such as labor and materials, and _indirect costs_, such as leaseholds, penalties and bonuses, or organizational overheads @Hosseinpour2023 @Agarwal2013. 

#v(1em)
#figure(
  cetz.canvas({
    import cetz.draw: *

    // --------------------------------------------------------
    // 1. Generate Mathematical Data Points
    // --------------------------------------------------------

    // Indirect cost: linear increasing, sampled over the full visible domain
    let pts-indirect = range(15, 56).map(i => {
      let x = i / 10.0
      (x, 0.5 * (x - 3.0) + 2.0)
    })

    // Direct cost: rational decay, sampled over the full visible domain
    let pts-direct = range(15, 56).map(i => {
      let x = i / 10.0
      (x, 3.125 / (x - 0.5) + 0.75)
    })

    // Total cost: exact sum, widened so the curve actually reaches the
    // "Total cost" label near the upper right (and is symmetric-ish
    // around the optimum), while still looking slightly cropped like
    // the textbook figure
    let pts-total = range(17, 55).map(i => {
      let x = i / 10.0
      (x, (0.5 * (x - 3.0) + 2.0) + (3.125 / (x - 0.5) + 0.75))
    })

    // --------------------------------------------------------
    // 2. Axes
    // --------------------------------------------------------

    line((0, 0), (6.5, 0), mark: (end: ">"), stroke: 0.6pt)
    line((0, 0), (0, 5.5), mark: (end: ">"), stroke: 0.6pt)
    content((6.65, 0), text(size:9pt)[Time], anchor: "west")
    content((0, 5.65), text(size:9pt)[Cost], anchor: "south")

    // --------------------------------------------------------
    // 3. Curves — monochrome, distinguished by dash pattern only
    // --------------------------------------------------------

    // Indirect cost: dashed
    line(..pts-indirect, stroke: (paint: black, thickness: 0.5pt, dash: "dashed"))

    // Direct cost: dotted
    line(..pts-direct, stroke: (paint: black, thickness: 0.5pt, dash: "dashed"))

    // Total cost: solid, marginally thicker so it reads as the "main" curve
    line(..pts-total, stroke: (paint: black, thickness: 0.8pt))

    // --------------------------------------------------------
    // 4. Optimum guide line + axis ticks
    // --------------------------------------------------------

    // Dropped guide line from the minimum of Total cost to the x-axis
    line((3.0, 0), (3.0, 4.0), stroke: (paint: black, thickness: 0.4pt, dash: "dotted"))

    // X-axis ticks: Dc, Optimum, Dn
    line((1.5, 0.1), (1.5, -0.1), stroke: 0.5pt)
    content((1.5, -0.35), text(size:9pt)[$D_c$], anchor: "north")

    line((5.5, 0.1), (5.5, -0.1), stroke: 0.5pt)
    content((5.5, -0.35), text(size:9pt)[$D_n$], anchor: "north")

    // Y-axis ticks: Cc, Cn
    // Cc aligns with the start of the Indirect cost curve (x = 1.5)
    line((0.1, 1.25), (-0.1, 1.25), stroke: 0.5pt)
    content((-0.3, 1.25), text(size:9pt)[$C_c$], anchor: "east")

    // Cn aligns with the start of the Direct cost curve (x = 1.5)
    line((0.1, 3.875), (-0.1, 3.875), stroke: 0.5pt)
    content((-0.3, 3.875), text(size:9pt)[$C_n$], anchor: "east")

    // --------------------------------------------------------
    // 5. Curve labels
    // --------------------------------------------------------

    content((5.55, 4.7), text(size:9pt)[Total Cost], anchor: "west")
    content((5.675, 3.35), text(size:9pt)[Indirect Cost], anchor: "west")
    content((5.65, 1.375), text(size:9pt)[Direct Cost], anchor: "west")
  }),
  caption: [Time--Cost Tradeoffs],
  gap: 1em
) <fig:time-cost>
#v(1em)

The interplay between both cost types yields a nontrivial time--cost tradeoff (see @fig:time-cost). Hence, #sans("TCTP")s most naturally employ _multi-objective_ functions @Agarwal2013. However, scalarization into a single--objective is also common @orm2018, due to its computational friendliness and practical explainability. Finally, we comment that though #sans("TCTP")s consider only time and cost, some models extend this to other objectives. Most notable examples include quality (#sans("TCQTP")s), safety (#sans("TCQSTP")s), and energy--environment (#sans("TCQEETP")s) @Herroelen2001 @orm2018. 

== Optimization Methods

Naive project scheduling traditionally uses critical path methods (CPM) to attain a solution in polynomial time @kelley1961. Unfortunately, it is well known that the resource--constraints of #sans("RCPSP")s make it an NP--hard problem, as shown in @blazewicz1983. Thus, the selection of optimization method is an essential part of project scheduling modelling. In this section, we will give a brief overview of the most popular methods for #sans("RCPSP")s that will be relevant to us later. 

First, we consider some exact methods. As identified in @Artigues2026, mixed--integer linear programming (MILP) and constraint programming (CP) are the most prominent modern formulations of #sans("RCPSP")s. The former is most suitable for mode--based decisions, while the latter seems to be more flexible. _Branch and bound_ techniques (B&B) and their extensions have proven to be one of the most widely--used exact methods, as it is very applicable for both MILPs and CPs. Common branching techniques are based on precedence trees, delay alternatives, schedule schemes, and more @Brucker1999. On the other hand, we also highlight the utility of boolean satisfiability (SAT) solvers for CP formulations, as CP/SAT approaches currently yield state--of--the--art results in many problems @Artigues2026. 

Next, we study some non--exact methods. Early heuristic methods are often simple priority rules that, though easy to implement, are not very reliable @Brucker1999. Hence, non--exact methods have only been widely adopted in #sans("RCPSP")s relatively recently in the 1990s. Genetic algorithms (GA) are the most notable metaheuristic methods for #sans("RCPSP")s @Artigues2026, though particle swarm optimization (PSO) and ant colony optimization (ACO) are also popular @merkle2002 @zhang2005. Otherwise, machine learning has also been attempted in #sans("RCPSP")s with various success, but mainly set back by the computational cost of training @Artigues2026. 

= Models

To motivate our #sans("RC-TCTP") formulations, we shall begin with a novel model whose objective utilizes the Cobb--Douglas production function to estimate project costs without requiring known crash costs. The non--linearity of the Cobb--Douglas utility motivates a genetic algorithm (GA) approach that proved to be inefficient. To solve this, we simplify the model in two ways. First, we construct a mode--based variant employing mixed--integer linear programming (MILP). Second, we also created a time--based variant through interpolation of cost and resource slopes. Both will be formulated under a constrained programming (CP) language, which allows the use of efficient boolean satisfiability (SAT) techniques. Though the two alternatives might not seem very motivated as of now, we will later derive them as very natural reductions of the original Cobb--Douglas formulation. 

== Resource--Based Model

The development of #sans("TCTP") models that do not rely on the assumption of known crash costs is relatively recent. In particular, we focus on those with resource--based decisions (see Section 1.2), as it is most natural to rigorously estimate crash costs from resource allocation when costs are unknown. Binary selection of fixed indivisible crews is a popular approach, as applied in Tomczak and Jaśkowski @tomczak2024 for general project scheduling or Jaśkowski et al. @jaskowski2025 for project crashing specifically. This is often embellished with clever lag or reordering variables for more dynamic results despite being discrete. On the other hand, there are also continuous formulations. For instance, the landmark model by Naber & Kolisch @naber2014 was among the first to use continuous knobs for daily allocation of resources  . However, we find the work of Jeunet et al. @jeunet2020 to be most pertinent, as it specifically uses the number of workers and number of overtime as continuous decision variables. Our model shall take a similar approach in the use of overmanning and overtime decisions. However, while Jeunet et al. @jeunet2020 simulate inefficiencies using a productivity multiplier, we will employ the Cobb--Douglas production function. 

The Cobb--Douglas production function, sometimes called the Cobb--Douglas utility, was first engineered by Cobb and Douglas in 1928 @cobb1928 to measure the large--scale effect of labor and capital on the volume of US manufactured goods. A modern formulation of the Cobb--Douglas production function can be written as 

$ Y(L,K) = A L^alpha K^beta, $ <eq:cobb-douglas>

#noindent where $Y$ is production output, $L$ is labor, $K$ is capital, and $A$ is the productivity factor. Here, $alpha$ and $beta$ are parameters called labor and capital elasticity respectively, such that the Cobb--Douglas function is homogeneous of degree $alpha + beta$, which determines the type of _returns to scale_ @jacques2018. Hence, we see that it is originally a macroeconomic model. However, it has also been utilized in modelling smaller scale outputs too such as efficiencies of individual banks @hasan2012, crop output of individual farms @kloss2019, or even treated patients of individual hospitals @reyessantias2020 with great success. 

In fact, we spotlight the use of the Cobb--Douglas function in project crashing done by Shen et al. @shen2016, which we later discovered to be very similar in spirit to our model. Their model employed crew labor and project equipment as $L$ and $K$ variables, such that the construction rate follows the Cobb--Douglas formulation and the objective is their weighted sum. Here, the workload $W$ of a task is fixed, such that the construction rate $Q$ required to attain a crashed duration $t$ is $Q = W\/t$. It is summarized in the following optimization problem:

$ 
min_(L,K)  quad & c_1 L + c_2 K, \
"subject to" quad & W\/t = L^(1-alpha)K^(alpha), \
             quad & L, K >= 0.
$

#noindent Note that the above can be solved analytically with the method of _Lagrange multipliers_. Yet as we will see, though our model uses a similar application of the Cobb--Douglas production function, it notably differs in its objective, which presents new computational challenges. 

=== Model Formulation

Suppose we are given a baseline project schedule consisting of activities $I$ and resources $K$. Each activity $i in I$ possesses a start time $s_i in RR$ counted relative to the very start of the schedule. Each activity is executed by certain resources, as facilitated by a fixed workload $W_(i,k)^((0))$ and allocation $U_(i,k)$ that is required of resource $k in K$ for activity $i in I$. Under the assumption that each unit of resource works $8$ hours a day, we calculate the baseline effective duration for activity $i in I$ due to resource $k in K$ as

$ d_(i,k)^((0)) := W_(i,k)^((0))/(8 U_(i,k)), $ <eq:duration-original>

#noindent such that the actual baseline duration and end time of activity $i in I$ is obtained from

$ 
d_i^((0)) := max_(k in K) d_(i,k)^((0)), 
quad quad 
e_i^((0)) = s_i + d_i^((0)),
quad quad
forall i in I.
$ <eq:schedule-original>

#noindent Next, given an hourly wage $r_k$ for each resource $k in K$, we have that the quantity

$ z_(i,k)^((0)) := d_(i,k)^((0)) dot U_(i,k) dot 8 dot r_k = W_(i,k)^((0)) dot r_k, $ <eq:cost-original>

#noindent represents the baseline costs required for resource $k in K$ in activity $i in I$. Therefore, we have obtained the mathematical engine that calculates the schedule and its costs (given just activity start durations, fixed workload and allocations, as well as wages). 

#align(center)[
  #show figure.where(kind: table): set block(breakable: true)
  #v(1em)
  #set text(size: 8.8pt)
  #figure(
    table(
      columns: (auto, auto, 1fr),
      align: (left, left, left),
      stroke: none,
      inset: 0.5em,
  
      table.header(
        table.hline(stroke: 1pt),
        [*Symbol*], [*Unit*], [*Description*],
        table.hline(stroke: 1pt),
        table.cell(colspan: 3, inset: 0pt, v(5pt))
      ),
      
      // Sets
      table.cell(colspan: 3, align: left)[_Sets_],
      [$I$], [--], [Indices of activities $i$],
      [$I_0$], [--], [Activities with $e_i^((0)) <= T_0$ (already completed)],
      [$I_1$], [--], [Activities with $s_i^((0)) >= T_0$ (not yet started)],
      [$E_"FS", E_"SS", E_"FF"$], [--], [Finish-to-start, start-to-start, and finish-to-finish precedence relations],
      [#pad(bottom: 5pt)[$K$]], [--], [Indices of resources $k$],
      table.hline(stroke: 0.6pt),
      
      // Data Parameters
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Data Parameters_]],
      [$W_(i,k)^((0))$], [unit--hours], [Baseline work effort of resource $k$ on activity $i$],
      [$s_i^((0))$], [days], [Baseline start time of activity $i$],
      [$delta_(i j)$], [days], [Lag or lead between activities $i$ and $j$],
      [$U_(i,k)$], [units], [Baseline daily allocation of resource $k$ on activity $i$],
      [$U_k^(max)$], [units], [Available capacity of resource $k$ per day],
      [$r_k$], [\$/hour], [Regular wage rate of resource $k$],
      [$r'_k$], [\$/hour], [Overtime wage rate of resource $k$ with $r'_k >= r_k$],
      [$p_i$], [--], [Fraction of activity $i in I_0^C inter I_1^C$ that is completed ($0 < p_i < 1$)],
      [$T_max$], [days], [Day of project deadline],
      [#pad(bottom: 5pt)[$T_0$]], [days], [Current day of project review],
      table.hline(stroke: 0.6pt),

      // Model Parameters
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Model Parameters_]],
      [$alpha$], [--], [Cobb–Douglas labor elasticity for overcrowding ($0 < alpha < 1$)],
      [$beta$], [--], [Cobb–Douglas capital elasticity for overtime ($0 < beta < 1$)], 
      [$x_max$], [--], [Maximum overmanning multiplier], 
      [$tau_max$], [hours/day], [Maximum overtime addend], 
      [$gamma$], [--], [Minimum crashable fraction of baseline duration $(0 < gamma < 1)$], 
      [$c_"late"$], [\$/day], [Late completion penalty],
      [#pad(bottom: 5pt)[$c_"early"$]], [\$/day], [Early completion bonus],
      table.hline(stroke: 0.6pt),

      // Auxiliary Variables
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Auxiliary Variables_]],
      [$d_(i,k)^((0))$], [days], [Baseline effective duration of activity $i$ driven by resource $k$],
      [$d_i^((0))$], [days], [Baseline duration of activity $i$],
      [$e_i^((0))$], [days], [Baseline end time of activity $i$],
      [$z_(i,k)^((0))$], [\$], [Baseline total cost of resource $k$ in activity $i$],
      [$W_(i,k)$], [unit--hours], [Work effort of resource $k$ on activity $i$],
      [$d_(i,k)$], [days], [Effective duration of activity $i$ driven by resource $k$],
      [$d_i$], [days], [Duration of activity $i$],
      [$e_i$], [days], [End time of activity $i$],
      [#pad(bottom: 5pt)[$z_(i,k)$]], [\$], [Total cost of resource $k$ in activity $i$],
      table.hline(stroke: 0.6pt),
  
      // Decision Variables
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Decision Variables_]],
      [$x_(i,k)$], [--], [Overmanning multiplier for resource $k$ on activity $i$],
      [$tau_(i,k)$], [hours/day], [Overtime addend for resource $k$ on activity $i$],
      [$s_i$], [days], [Start time of activity $i$],
      
      table.footer(
        table.cell(colspan: 3, inset: 0pt, v(5pt)), 
        table.hline(stroke: 1pt)
      ),
    ), 
    caption: [Summary of Resource--Based Model Notations],
    gap: 1em,
  ) <fig:notation-1>
  #v(1em)
]

We now turn to the question of _crashing_ the given baseline project schedule. This builds our primary model. First, notice that the duration formula of @eq:duration-original provides two natural ways to perform resource--based crashing: increasing the daily work hours and increasing the allocated units. In physical terms, this might correspond to _overtime_ and _overmanning_. A naive way of doing this would be to write 

$ d_(i,k) (x_(i,k), tau_(i,k)) = W_(i,k) / ((8 + tau_(i,k))(x_(i,k) U_(i,k))), $

#noindent where we emphasize $d_(i,k)$ as a function of $x_(i,k)$ and $tau_(i,k)$, which represents the multiplicative overmanning and additive overtime supplements respectively. A plausible domain constraint for these two decisions might be 

$ 1 <= x_(i,k) <= x_max, quad quad 0 <= tau_(i,k) <= tau_max, quad quad forall i in I, forall k in K, $ <eq:domain-1>

#noindent where the continuity of $x_(i,k)$ is justified by the possibility of fractional workloads (e.g., $5.5$ units might denote five full--time workers and one part--time worker). Further explanation for value of the workload $W_(i,k)$ in the above formula for $d_(i,k)$ will be detailed later. For now, notice that 

$ z_(i,k) = d_(i,k) dot x_(i,k) U_(i,k) dot (8 + tau_(i,k)) dot r_k = W_(i,k) r_k = z_(i,k)^((0)) $

#noindent which is no different than the baseline cost of @eq:cost-original. This is a problem, as it implies crashing incurs no additional costs, which is only true if one assumes perfect efficiencies in overmanning and overtime of workers. We resolve this issue using the Cobb--Douglas production function. Observe that the denominator of @eq:duration-original is essentially a productivity measure (unit--hours per day). Applying the Cobb--Douglas form in @eq:cobb-douglas, we instead write 

$ d_(i,k) (x_(i,k), tau_(i,k)) = W_(i,k) / (A_(i,k) (x_(i,k) U_(i,k))^alpha (8 + tau_(i,k))^beta), $

#noindent where $alpha$ and $beta$ represents the elasticity of overmanning and overtime. Hence, allocation units correspond to labor while work hours correspond to capital. Then, one can easily verify that the selection of productivity factor

$ A_(i,k) = U_(i,k)^(1-alpha) 8^(1-beta) $ 

#noindent guarantees that $d_(i,k) = d_(i,k)^((0))$ when $x_(i,k)=1$ and $tau_(i,k)=0$, which is an intuitive choice. Substitution yields the expanded duration formula

$ 
d_(i,k) (x_(i,k), tau_(i,k)) = 
underbrace(W_(i,k) / (8 U_(i,k)), d_(i,k)^((0))) dot
underbrace((1 / x_(i,k))^alpha, "overcrowd") dot 
underbrace((8 / (8 + tau_(i,k)))^beta, "overwork"),
$ <eq:duration-new>

#noindent such that @eq:schedule-original naturally translates into 

$ 
d_i := max_(k in K) d_(i,k) (x_(i,k), tau_(i,k)), 
quad quad e_i = s_i + d_i,
quad quad forall i in I.
$ <eq:schedule-new>

#noindent Notice the Cobb--Douglas approach thus captures inefficiencies corresponding to overmanning and overtime crashing strategies, such as "overcrowding" the project site or "overworking" the resource crew. This is further reflected in the total cost calculation, which can be rewritten as the following: 

$ 

z_(i,k)(x_(i,k), tau_(i,k)) 
&= d_(i,k) (x_(i,k), tau_(i,k)) dot x_(i,k) U_(i,k) dot (8 r_k + tau_(i,k) r'_k) \ 

&= W_(i,k) / (8 U_(i,k)) dot (1 / x_(i,k))^alpha dot (8 / (8 + tau_(i,k)))^beta dot x_(i,k) U_(i,k) dot (8 r_k + tau_(i,k) r'_k) \

&= W_(i,k) dot x_(i,k)^(-alpha) dot x_(i,k) dot ((8 + tau_(i,k)) / 8)^(-beta) dot (8 + tau_(i,k)) / 8 dot 1 / (8 + tau_(i,k)) dot (8 r_k + tau_(i,k) r'_k) \

&= 
underbrace(W_(i,k) r_k, z_(i,k)^((0))) dot 
underbrace(x_(i,k)^(1-alpha), "overcrowd") dot 
underbrace(((8 + tau_(i,k)) / 8)^(1-beta), "overwork") dot 
underbrace((8 + r'_k / r_k tau_(i,k)) / (8 + tau_(i,k)), "extra wage"), 

$ <eq:cost-new>

#noindent This beautifully differs from @eq:cost-original with clear overmanning and overtime factors, which completely resolves the issues of the naive approach. Observe that a factor represents extra wage is present regardless of any inefficiencies in overmanning or overtime. Finally, we note that $r'_k$ above denotes premium overtime wage rates and that we keep the domain constraints of @eq:domain-1 throughout. 

*Temporal Constraints.* Subsequently, we can now turn our attention to the temporal and resource constraints that characterize this problem as a #sans("RC-TCTP"). Firstly, suppose we have precedence relations $E_"FS", E_"SS", E_"FF"$ that correspond to finish--to--start, start--to--finish, and finish--to--finish relations. These are mathematically interpreted as the edges of the project schedule graphs whose vertex set is $I$. We then require 

$ 
  s_j >= e_i + delta_(i j), quad forall (i,j) in E_"FS", \
  s_j >= s_i + delta_(i j), quad forall (i,j) in E_"SS", \
  e_j >= e_i + delta_(i j), quad forall (i,j) in E_"FF". 
$ <eq:temporal-constraint>

#noindent Furthermore, we limit the crashing abilities of the model by bounding the new post--crash duration $d_(i,k)$ below by some fraction $gamma$ of the baseline duration $d_(i,k)^((0))$. Formally, we write 

$ d_(i,k) (x_(i,k), tau_(i,k)) >= gamma dot d_(i,k)^((0)), quad quad forall i in I, forall k in K. $ <eq:duration-constraint>

*Resource Constraints.* Secondly, suppose further that each resource $k in K$ has a maximum capacity $U_k^max$ of usable units. We capture this resource constraint by checking that the total usage of resource $k in K$ does not exceed $U_k^max$ at the start of every task (this guarantees the constraint is also satisfied throughout the entire project if we assume non--preemptiveness, which is standard in #sans("RCPSP")s). This is possible using an indicator variable as follows:

$ sum_(i in I) x_(i,k) U_(i,k) dot bb(1) \{ s_i <= s_j < s_i + d_(i,k) \} <= U_k^(max), quad forall k in K, forall j in I. $ <eq:resource-constraint>

#noindent Recognize the use of $s_i + d_(i,k)$ in the indicator instead of $e_i$, which allows the possibility that a resource $k in K$ finishes its job early (or begins its job late) in activity $i in I$ if it has relatively small workload in that task. In any case where this might be an unreasonable assumption, replacement by $e_i$ is perfectly possible (and much simpler). 

*Crashing Constraints.* Furthermore, suppose that the construction project has a deadline $T_max in RR$ that the baseline schedule is projected to exceed given the present review day $T_0 in RR$. We can thus partition the activities $I$ into those that have completed $I_0$ and have not started $I_1$. This allows for three task types. Activities that have not commenced are crashable with its full workload, such that

#align(center)[
  $ #grid(
    columns: 2,
    align: (center, horizon), 
    [
      #set math.equation(numbering: none)
      $ 
        W_(i,k) = W_(i,k)^(\(0\)) \
        s_i >= T_0, \
        1 <= x_(i,k) <= x_max, \
        0 <= tau_(i,k) <= tau_max 
      $
    ],
    [
      #set math.equation(numbering: none)
      $ quad quad forall k in K, forall i in I_1. $
    ]
  ) $ <eq:not-started-constraint>
] 

#noindent On the other hand, activities that are fully completed are not crashable. Every variable and parameter is set to its baseline schedule, that is, 

#align(center)[
  $ #grid(
    columns: 2,
    align: (center, horizon), 
    [
      #set math.equation(numbering: none)
      $ 
        W_(i,k) = W_(i,k)^(\(0\)) \
        s_i = s_i^(\(0\)), \
        x_(i,k) = 1, \
        tau_(i,k) = 0, 
      $
  ],
    [
      #set math.equation(numbering: none)
      $ quad quad forall k in K, forall i in I_0. $
    ]
  ) $ <eq:completed-constraint>
]

#noindent Finally, activities $i in I$ that have only been partially finished, say up to a proportion $p_i in [0,1]$, can only be crashed proportionally as follows:

#align(center)[
  $ #grid(
    columns: 2,
    align: (center, horizon), 
    [
      #set math.equation(numbering: none)
      $ 
        W_(i,k) = W_(i,k)^(\(0\))(1 - p_i) \
        s_i = s_i^(\(0\)), \
        1 <= x_(i,k) <= x_max, \
        0 <= tau_(i,k) <= tau_max, 
      $
    ],
    [
      #set math.equation(numbering: none)
      $ quad quad forall k in K, forall i in I_0^C inter I_1^C. $
    ]
  ) $ <eq:started-not-completed-constraint>
]

*Project Objectives.* At last, we consider the project objective. As common in #sans("RC-TCTP") models, we first consider a time--cost multi--objective. Let $s_(n+1)$ be the project completion day of the schedule. Mathematically, it may be equivalently regarded as the start time of an $(n+1)$--th auxiliary task with the property that every other activity precedes it, often called a _sink activity_. Hence, we consider the multi--objective function

$ 
min (s_(n+1), sum_(i in I) sum_(k in K) z_(i,k)(x_(i,k), tau_(i,k))), 
$ <eq:multi-objective-1>

#noindent Nevertheless, we also consider a scalarization of this objective using a bonus--penalty approach. One can reward early project completions and punish late project completions using a fixed penalty $c_"late"$ and bonus $c_"early"$ daily rate. This turns the hard constraint into a soft constraint: 

$ 
min sum_(i in I) sum_(k in K) z_(i,k)(x_(i,k), tau_(i,k)) + c_"late" max(0, s_(n+1) - T_"max") - c_"early" max(0, T_"max" - s_(n+1)). 
$ <eq:single-objective-1>

#noindent We shall experiment with both objectives. Consequently, the objective functions @eq:multi-objective-1 and @eq:single-objective-1, subject to the labeled constraints @eq:duration-constraint through @eq:started-not-completed-constraint, completely characterize the #sans("RC-TCTP") model we have formulated. Activity start times $s_i$, overmanning multipliers $x_(i,k)$, and $tau_(i,k)$ are the decision variables. A comprehensive summary of all the notations used in this model is displayed in @fig:notation-1. 

=== Optimization Method 

To solve the proposed #sans("RC-TCTP"), we first observe the highly non--linear nature of the model, exemplified by the use of power functions and binary indicators. This classifies the problem as _mixed--integer non--linear programming_ (MINLP). Thus, metaheuristic approaches are much more appealing than exact methods. In particular, we present the use of a Genetic Algorithm (GA) and its extension to multi--objectives like _Non--dominated Sorted Genetic Algorithm II_ (NSGA--II). A similar GA approach has been applied to for much simpler Cobb--Douglas objectives in @dinc2025, which showed its competitiveness with exact Lagrangian methods in this non--linear scenario. On the other hand, the landmark use of GA in the #sans("RCPSP") setting was done by Hartmann in 1998 @hartmann1998, where GA was used to determine the order of tasks while a _Serial Scheduling Scheme_ (SSS) builds the schedule out of said order. We shall employ an analogous approach for our case. 



In particular, we apply a genetic algorithm to determine overmanning multipliers, overtime addends, and activity order priority. Mathematically, this is achieved with chromosomes consisting of $2|I|dot|K|+|I|$ genes, with genes $1$ to $|I|dot|K|$ representing the overmanning multipliers, genes $|I|dot|K|+1$ to $2|I|dot|K|+1$ representing overtime addends, and remaining genes representing activity order priority. We note that activity order priority is a continuous variable in $[0,1]$ for each activity. Furthermore, in practice, activity---resource pairs $(i,k)$ with $U_(i,k)=0$ are also omitted to simplify the chromosome. Uniform initialization between appropriate upper and lower bounds of each gene is used. Then, evolution operates under standard tournament selection, simulated binary crossover, and polynomial mutation. These strategies are implemented in `pymoo`, a Python framework used for optimization. 

The generated activity order priority is then built into a schedule using a serial scheduling scheme. This is a deterministic process that involves selecting tasks with the highest priority to come first and following them with the most immediate successors. With this, start times $s_i$ are pushed forward as much as possible. Whenever the resource--constraint is not satisfied, the scheme shifts activities accordingly. Once the schedule is built, costs can be calculated using the objective, which acts as a fitness score for the associated chromosome. The described algorithm easily generalizes to the multi--objective case. 

== Mode--Based Model 

Now, we consider the challenge of simplifying the complex resource--based model. Though more efficient than exact methods for complex problems, genetic algorithms remain notoriously slow in many settings. Thus, we first propose a discretization of the model developed in Section 2.1. As surveyed in Section 1.2, _multi--mode_ #sans("RCPSP")s, often denoted #sans("MRCPSP")s, is one of the most popular formulations of project scheduling. Talbot first formalized #sans("MRCPSP")s in 1982 @talbot1982, where each mode corresponds to different resource allocations, activity durations, and thus costs. Here, we shall do a similar reduction of the original model into modes. 

=== Model Formulation

Suppose we partition our overmanning $[1,x_max]$ and overtime $[0,tau_max]$ domains into $M$ and $N$ intervals respectively. For simplicity, denote $[0,M]_NN := {0,...,M}$, $[0,N]_NN := {0, ..., N}$, and $cal(M) := [0,M]_NN times [0,N]_NN$. Then, for all $(m,n) in cal(M)$, we define

$ 
x_(i,k)^((m)) = 1 + m/M (x_max - 1) 
quad " and " quad 
tau_(i,k)^((n)) = n/N tau_max.
$

#noindent Hence for every activity $i in I$ and resource $k in K$, each pair $(m,n) in cal(M)$ corresponds to a _mode_ of crashing that can be chosen: the $m$--th overmanning multiplier $x_(i,k)^((m))$ and $n$--th overtime addend $tau_(i,k)^((n))$. This reduces the continuous formulation of the original model into a discrete problem.  

Moreover, denote by $xi_(i,k)^((m,n))$ the binary indicator for the mode selection $(m,n) in cal(M)$ for resource $k$ in activity $i$. This now acts as our new decision variable. We can calculate the activity duration and cost associated with the selection. Following @eq:duration-new, one obtains the corresponding duration is

$ 
  d_(i,k)^((m,n)) = 
  underbrace(W_(i,k) / (8 U_(i,k)), d_(i,k)^((0))) dot
  underbrace((1 / x_(i,k)^((m)))^alpha, "overcrowd") dot 
  underbrace((8 / (8 + tau_(i,k)^((n))))^beta, "overwork"),
$ <eq:duration-mode>

#noindent while following @eq:cost-new, the corresponding cost is

$ 
  z_(i,k)^((m,n)) &= 
  underbrace(W_(i,k) r_k, z_(i,k)^((0))) dot 
  underbrace((x_(i,k)^((m)))^(1-alpha), "overcrowd") dot 
  underbrace(((8 + tau_(i,k)^((n))) / 8)^(1-beta), "overwork") dot 
  underbrace((8 + r'_k / r_k tau_(i,k)^((n))) / (8 + tau_(i,k)^((n))), "extra wage"). 
$ <eq:cost-mode>

#noindent All $|I| times |K| times M times N$ values of both quantities can be _precomputed_ for a given review day $T_0$ (of course for dynamic reviews, this precomputation must be recalculated every time). Therefore, a lot of parameters will no longer be needed, as they can be compressed into local parameters for each $(m,n) in cal(M)$ pair. Now, we are left to translate the constraints and objectives of Section 2.1 into this mode--based approach. Most will be preserved, but some require modification. 

#align(center)[
  #show figure.where(kind: table): set block(breakable: true)
  #v(1em)
  #set text(size: 8.8pt)
  #figure(
    table(
      columns: (auto, auto, 1fr),
      align: (left, left, left),
      stroke: none,
      inset: 0.5em,

      table.header(
        table.hline(stroke: 1pt),
        [*Symbol*], [*Unit*], [*Description*],
        table.hline(stroke: 1pt),
        table.cell(colspan: 3, inset: 0pt, v(5pt))
      ),

      // Sets
      table.cell(colspan: 3, align: left)[_Sets_],
      [$I$], [--], [Indices of activities $i$],
      [$I_0$], [--], [Activities with $e_i^((0)) <= T_0$ (already completed)],
      [$I_1$], [--], [Activities with $s_i^((0)) >= T_0$ (not yet started)],
      [$E_"FS", E_"SS", E_"FF"$], [--], [Finish-to-start, start-to-start, and finish-to-finish precedence relations],
      [$K$], [--], [Indices of resources $k$],
      [#pad(bottom: 5pt)[$cal(M)'$]], [--], [Pruned indices of crashing modes $(m,n)$],
      table.hline(stroke: 0.6pt),

      // Data Parameters
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Data Parameters_]],
      [$U_(i,k)$], [units], [Baseline daily allocation of resource $k$ on activity $i$],
      [$U_k^(max)$], [units], [Available capacity of resource $k$ per day],
      [$delta_(i j)$], [days], [Lag or lead between activities $i$ and $j$],
      [$T_max$], [days], [Day of project deadline],
      [#pad(bottom: 5pt)[$T_0$]], [days], [Current day of project review],
      table.hline(stroke: 0.6pt),

      // Model Parameters
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Model Parameters_]],
      [$c_"late"$], [\$/day], [Late completion penalty],
      [#pad(bottom: 5pt)[$c_"early"$]], [\$/day], [Early completion bonus],
      table.hline(stroke: 0.6pt),

      // Auxiliary Variables
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Auxiliary Variables_]],
      [$x_(i,k)^((m))$], [--], [Precomputed overmanning multiplier for mode $m$],
      [$d_(i,k)^((m,n))$], [days], [Precomputed effective duration for mode $(m,n)$],
      [$z_(i,k)^((m,n))$], [\$], [Precomputed cost for mode $(m,n)$],
      [$u_(i,k)$], [units], [Selected daily allocation of resource $k$ on activity $i$],
      [$d_(i,k)$], [days], [Effective duration of activity $i$ driven by resource $k$],
      [$d_i$], [days], [Duration of activity $i$],
      [#pad(bottom: 5pt)[$e_i$]], [days], [End time of activity $i$],
      table.hline(stroke: 0.6pt),

      // Decision Variables
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Decision Variables_]],
      [$xi_(i,k)^((m,n))$], [--], [Binary selector of mode $(m,n)$ for resource $k$ on activity $i$],
      [$s_i$], [days], [Start time of activity $i$],

      table.footer(
        table.cell(colspan: 3, inset: 0pt, v(5pt)),
        table.hline(stroke: 1pt)
      ),
    ),
    caption: [Summary of Mode--Based Model Notations],
    gap: 1em,
  ) <fig:notation-2>
  #v(1.25em)
]

*Project Objective.* To begin, we notice that the total cost of the entire construction now depends on both the selected mode and its precomputed cost. Therefore, the multi--objective of @eq:multi-objective-1 is translated into 

$ 
min (s_(n+1), sum_(i in I) sum_(k in K) sum_((m,n) in cal(M)) z_(i,k)^((m,n)) xi_(i,k)^((m,n)) ), 
$ <eq:multi-objective-2>

#noindent while the bonus--penalty based single--objective of @eq:single-objective-1 is translated into

$ 
min sum_(i in I) sum_(k in K) sum_((m,n) in cal(M)) z_(i,k)^((m,n)) xi_(i,k)^((m,n)) + c_"late" max(0, s_(n+1) - T_"max") - c_"early" max(0, T_"max" - s_(n+1)). 
$ <eq:single-objective-2>

#noindent Here, since the values of $z_(i,k)^((m,n))$ have been precomputed, the calculation of the total cost has been linearized. This offers new opportunities in its computation method. 

*Mode Assignment.* A constraint standard but unique to #sans("MRCPSP")s is the _uniqueness_ of the mode assignment. That is, for each activity $i in I$ and resource $k in K$, one can only choose a single mode type $(m,n) in cal(M)$. Mathematically, we simply require that 

$ sum_((m,n) in cal(M)) xi_(i,k)^((m,n)) = 1, quad quad forall i in I, forall k in K. $ <eq:mode-constraint>

*Temporal Constraints.* Firstly, notice that the effective duration @eq:duration-new must be translated into

$ d_(i,k) = sum_((m,n) in cal(M)) d_(i,k)^((m,n)) xi_(i,k)^((m,n)). $ <duration-mode>

#noindent With this formula, the lower bound of @eq:duration-constraint 

$ d_(i,k) >= gamma dot d_(i,k)^((0)), quad quad forall i in I, forall k in K, $ <eq:duration-constraint-mode> 

#noindent the auxiliary variables of @eq:schedule-new  

$ 
d_i := max_(k in K) sum_((m,n) in cal(M)) d_(i,k)^((m,n)) xi_(i,k)^((m,n)), 
quad quad 
e_i = s_i + d_i, 
quad quad
forall i in I,
$ <eq:schedule-mode>

#noindent and the precedence constraints of @eq:temporal-constraint 

$ 
  s_j >= e_i + delta_(i j), quad forall (i,j) in E_"FS", \
  s_j >= s_i + delta_(i j), quad forall (i,j) in E_"SS", \
  e_j >= e_i + delta_(i j), quad forall (i,j) in E_"FF". 
$ <eq:temporal-mode>

#noindent are completely unchanged mathematically. Computationally, the discreteness of this model allows for optimizations that will be discussed later. 

*Resource Constraints.* We now turn to the resource constraint in @eq:resource-constraint. To rewrite this, we first define the selected daily allocation of resource $k in K$ at activity $i in I$ as

$ u_(i,k) := sum_((m,n) in cal(M)) xi_(i,k)^((m,n)) x_(i,k)^((m)) U_(i,k). $ <eq:allocate-mode>

#noindent With this, we can formally enforce the resource constraint as

$ sum_(i in I) u_(i,k) dot bb(1) \{ s_i <= s_j < s_i + d_(i,k) \} <= U_k^(max), quad forall k in K, forall j in I. $ <eq:resource-mode>

*Crashing Constraints.* Finally, the crashing constraints for which activities can be selected are translated as follows. Tasks which have not started as of the review day $T_0$ satisfy

#align(center)[
  $ #grid(
    columns: 2,
    align: (center, horizon), 
    [
      #set math.equation(numbering: none)
      $ 
        W_(i,k) = W_(i,k)^(\(0\)) \
        s_i >= T_0, \
        xi_(i,k)^((m,n)) in {0,1},
      $
    ],
    [
      #set math.equation(numbering: none)
      $ quad quad forall (m,n) in cal(M), forall k in K, forall i in I_1. $
    ]
  ) $ <eq:not-started-mode>
] 

#noindent Activities that are fully completed are not crashable, which implies

#align(center)[
  $ #grid(
    columns: 2,
    align: (center, horizon), 
    [
      #set math.equation(numbering: none)
      $ 
        W_(i,k) = W_(i,k)^(\(0\)) \
        s_i = s_i^(\(0\)), \
        xi_(i,k)^((m,n)) = bb(1){m=n=0},
      $
  ],
    [
      #set math.equation(numbering: none)
      $ quad quad forall (m,n) in cal(M), forall k in K, forall i in I_0. $
    ]
  ) $ <eq:completed-mode>
]

#noindent Finally, activities $i in I$ that have only been partially finished must follow

#align(center)[
  $ #grid(
    columns: 2,
    align: (center, horizon), 
    [
      #set math.equation(numbering: none)
      $ 
        W_(i,k) = W_(i,k)^(\(0\))(1 - p_i) \
        s_i = s_i^(\(0\)), \
        xi_(i,k)^((m,n)) in {0,1},  
      $
    ],
    [
      #set math.equation(numbering: none)
      $ quad quad forall (m,n) in cal(M), forall k in K, forall i in I_0^C inter I_1^C. $
    ]
  ) $ <eq:started-not-completed-mode>
]

Consequently, the objective function @eq:multi-objective-2 and @eq:single-objective-2, constrained by all of @eq:mode-constraint through @eq:started-not-completed-mode, make up the mode--based model. Furthermore, the mode selectors $xi_(i,k)^((m,n))$ and activity start times $s_i$ become the decision variables in this case. For a summary of the notations used for this model, see @fig:notation-2. 

=== Optimization Method 

As aforementioned, unlike the original resource--based approach, the objective of this mode--based model is linearized. Along with the binary modes but continuous start times, this classifies the established #sans("MRCPSP") as a _Mixed--Integer Linear Program_ (MILP). Standard optimization methods for MILPs often involve branch and bound techniques. Here we present a much more effective alternative based on _constraint programming_ (CP). The historical landmark introduction of CP techniques in #sans("RCPSP")s was done by Baptiste et al. in 2001 @baptiste2001. However, the _Constraint Programming Optimizer_ (CPO) by IBM ILOG was arguably more revolutionary, as its scheduling engine established an expressive interval--based modeling language for CPs for scheduling problems. In particular, it popularized the concept of _interval variables_ and _global constraints_ @laborie2009. Interval variables represent activities in our schedule, which have attributes like `start`, `end`, `size` (duration), and `presence` (execution). Global constraints are extremely specialized constraints that manage complex relations between arbitrary variables equipped with a specialized filtering algorithm. For our case, we shall reformulate our model in this expressive language, from which we can then employ CP algorithms. 

To begin, we prepare our model with some search space pruning. First, observe that in the duration precomputation of @eq:duration-mode, some might violate the lower bound in @eq:duration-constraint-mode. Second, for a fixed $i in I, k in K$, if a mode $(m,n) in cal(M)$ is such that there exists another mode $(m',n') in cal(M)$ satisfying

$ 
d_(i,k)^((m',n')) <= d_(i,k)^((m,n)), 
quad quad 
z_(i,k)^((m',n')) <= z_(i,k)^((m,n)), 
quad quad 
"and" 
quad quad
x_(i,k)^((m')) <= x_(i,k)^((m)), 
$

#noindent then the selection of the mode $(m,n)$ for the activity--resource pair will not yield the optimal solution, which we state without proof. Both methods allow us to prune the mode set $cal(M)$ during precomputation into a smaller subset $cal(M)'$. We shall use this pruned subset in implementation. 

With this, we are ready to rewrite our mode--based model in terms of the CPO interval--based language. Adopting the interval variable notation of @laborie2009 and global constraint notation of @gccat2014, one can view the decision $xi_(i,k)^((m,n))$ as an interval variable with  `start`, `end`, `size`, and `presence` attributes. Then, we will make use of the `cumulative` and `exactly` global constraints for our resource and uniqueness constraints respectively (see @gccat2014 for more information). This yields the constraint programming problem:

#[
  #set text(size: 9pt)
  $
    // Objective
    min       
    quad quad &   
    (
      s_(n+1), 
      sum_(i in I) sum_(k in K) sum_((m,n) in cal(M)) (
        z_(i,k)^((m,n)) dot #[`presence`#h(0em)] (xi_(i,k)^((m,n)))
      )
    ), \
    
    // Constraints
    "subject to"  
    quad quad & 
  
    // 1
    #[`exactly`#h(0em)] (
      1, 
      {#[`presence`#h(0em)] (xi_(i,k)^((m,n)))}, 
      1
    ),
    &forall i in I, forall k in K, \  
  
    // 2
    &#[`size`#h(0em)] (xi_(i,k)^((m,n))) = d_(i,k)^((m,n)), 
    &forall i in I, forall k in K, forall (m,n) in cal(M)', \ 
  
    // 3
    &#[`presence`#h(0em)] (xi_(i,k)^((m,n))) = 1 
    #h(0.5em) arrow.r.double.long #h(0.5em)
    #[`start`#h(0em)] (xi_(i,k)^((m,n))) = s_i,  
    &forall i in I, forall k in K, forall (m,n) in cal(M)', \
  
    // 4
    &e_i = op("max")_(k in K) (
      sum_((m,n) in cal(M)) 
      #[`presence`#h(0em)] (xi_(i,k)^((m,n))) dot 
      #[`end`#h(0em)] (xi_(i,k)^((m,n)))
    ), 
    quad 
    &forall i in I, \
  
    // 5
    &s_j >= e_i + delta_(i j), 
    &forall (i,j) in E_"FS", \
  
    // 6
    &s_j >= s_i + delta_(i j), 
    &forall (i,j) in E_"SS", \
  
    // 7
    &e_j >= e_i + delta_(i j), 
    &forall (i,j) in E_"FF", \
  
    // 8
    &#[`cumulative`#h(0em)] (
      #[`task`#h(0em)] ({
        xi_(i,k)^((m,n)),
        x_(i,k)^((m)) U_(i,k),
      }), 
      U_k^"max"
    ),  
    &forall k in K, \
  
    // 9
    &#[`presence`#h(0em)] (xi_(i,k)^((0,0))) = 1, s_i = s_i^((0)), 
    &forall i in I_0, \
  
    // 10
    &s_i >= T_0, 
    &forall i in I_1, \
  
    // 11
    &s_i = s_i^((0)),
    &forall i in I_0^C inter I_1^C.
  $
]

#noindent The formulation for the scalarized single--objective is the same. Regardless, this CP formulation shall be solved using a method developed by Google called _constraint programming satisfiability_ (CP-SAT). As commented in @Artigues2026, CP--SAT techniques can achieve state--of--the--art results in many #sans("RCPSP")s. This method is a hybrid of classical CP methods (like _constraint propagation_ and backtracking) and modern boolean satisfiability methods (like _conflict--driven clause learning_), bridged using a technique called _Lazy Clause Generation_ (LCG). For further explanation, we invite readers to @krupke2026. 

However, CP--SAT strictly requires integer domains, whether in its parameters or decision variables. To satisfy this, we will discretize certain variables by scaling and rounding. Variables get scaled before rounding to preserve floating point information. For instance, time representative variables are discretized by a scaling of $10^(ell_1)$ and an up--rounding of @eq:duration-mode, which yields

$ 
  d_(i,k)^((m,n)) = ceil(
    10^(ell_1) dot
    W_(i,k) / (8 U_(i,k)) dot
    (1 / x_(i,k)^((m)))^alpha dot
    (8 / (8 + tau_(i,k)^((n))))^beta
  ).
$ 

#noindent The up--rounding above is preferred to remain conservative (as longer durations are undesirable). Meanwhile, the $10^(ell_1)$ scaling maintains $ell_1$ decimal points of accuracy, from which the duration variables in the project objective must simply be scaled back down by $10^(ell_1)$ to recover the original scale. Other time variables such as start times $s_i$, end $e_i$ times, project review day $T_0$, and project deadline $T_max$ are treated with the same scaling. Thus, all decision variables have become integers. Cost representative variables are similarly discretized, with @eq:cost-mode being implemented as 

$ 
  z_(i,k)^((m,n)) &= floor( 
    10^(ell_2) dot
    W_(i,k) r_k dot 
    (x_(i,k)^((m)))^(1-alpha) dot 
    ((8 + tau_(i,k)^((n))) / 8)^(1-beta) dot 
    (8 + r'_k / r_k tau_(i,k)^((n))) / (8 + tau_(i,k)^((n)))
  )
$ 

#noindent Here, down--rounding is the conservative decision (as higher costs are undesirable). Analogously, we maintain $ell_2$ decimal points of accuracy, from which the total cost of the project objective must simply be scaled back down by $10^(ell_2)$ . 

== Time--Based Model 

Another simplification of the original #sans("RC-TCTP") formulation is a time--based approach. Recall that the first #sans("RCPSP") by @kelley1961 utilized duration as their decision variable, which required a known _crash slope_ (crash costs per unit of time crashed). Here, we propose a similar time--based model where costs are linearly related to reduced duration and the crash slope can be inferred from our Cobb--Douglas formulations. In fact, it is common to estimate cost functions by interpolation of the normal (minimum) and crashed (maximum) costs, as was done in @hu2024 and @kantianis2023 for quadratic and linear costs in #sans("RCPSP")s. In our case, these maximum and minimum sample points for interpolation will be obtained from the Cobb--Douglas production function. 

=== Model Formulation

To reduce the original resource--based formulation into a time--based model, we make the critical assumption that direct costs are linearly related to the _duration reduction_. For this, we shift our perspective into thinking duration is the decision variable. That is, for every activity $i in I$, its cost satisfies

$ z_i (d_i) = C_i (d_i^((0)) - d_i) + z_i^((0)), $ <eq:cost-linear>

#noindent where $C_i$ is a crash slope, $d_i^((0))$ is the baseline duration, $z_i^((0))$ is the baseline cost. The baseline duration follows @eq:schedule-original precisely, which we rewrite in its entirety here for clarity:

$ d_i^((0)) = max_(k in K) W_(i,k) / (8 U_(i,k)). $ <eq:duration-baseline>

#noindent Meanwhile, the baseline cost is simply derived from @eq:cost-original to be 

$ z_i^((0)) = sum_(k in K) z_(i,k)^((0)) = sum_(k in K) W_(i,k)^((0)) r_k. $ <eq:cost-baseline>

#noindent In contrast, the crash slope must be estimated differently. To do so, we first estimate the _maximum_ allowable crash for an activity $i in I$. Utilizing the resource--based Cobb--Douglas model, we can achieve this by maximizing $x_(i,k)$ and $tau_(i,k)$ for every $k in K$. Using @eq:duration-new, the crash limit is achieved at a duration 

$ 
  d_i^(("crash")) 
  &= max_(k in K) max(d_(i,k) (x_max, tau_max), gamma dot d_(i,k)^((0))) \
  &=max_(k in K) max(
    W_(i,k) / (8 U_(i,k)) dot
    (1 / x_max)^alpha dot 
    (8 / (8 + tau_max))^beta, 
  gamma dot d_(i,k)^((0))),
$ <eq:duration-crashed>

#noindent and by @eq:cost-new, is achieved at a cost 

$ 
  z_i^(("crash")) 
  &= sum_(k in K) z_(i,k) (x_max, tau_max) \
  &= max(d_(i,k) (x_max, tau_max), gamma dot d_(i,k)^((0))) dot x_(i,k) U_(i,k) dot (8 r_k + tau_(i,k) r'_k).
$ <eq:cost-crashed>

#noindent With the extremal values of cost and duration obtained, we now estimate the crash slope by dividing the extra cost associated with the crash limit by the total time saved:

$ 
C_i = cases(
  dfrac( z_i^(("crash")) - z_i^((0)) , d_i^((0)) - d_i^(("crash")) ) \, quad
  & "if" d_i^((0)) > d_i^(("crash")) \, ,
  0 \,
  & "if" d_i^((0)) = d_i^(("crash")).
) 
$ <eq:crash-slope>

#noindent Just like the mode--based model, these slope values can be _precomputed_ before running any schedule optimization. In fact, this approach fully abstracts away the underlying resource mechanisms, so that these extremal costs, extremal durations, and slopes must only be calculated $|I|$ times each, less than the mode--based precomputations. Of course, this comes at the price of the linearity assumption. With this, we are ready to formulate the time--based simplification. 

#align(center)[
  #show figure.where(kind: table): set block(breakable: true)
  #v(1em)
  #set text(size: 8.8pt)
  #figure(
    table(
      columns: (auto, auto, 1fr),
      align: (left, left, left),
      stroke: none,
      inset: 0.5em,

      table.header(
        table.hline(stroke: 1pt),
        [*Symbol*], [*Unit*], [*Description*],
        table.hline(stroke: 1pt),
        table.cell(colspan: 3, inset: 0pt, v(5pt))
      ),

      // Sets
      table.cell(colspan: 3, align: left)[_Sets_],
      [$I$], [--], [Indices of activities $i$],
      [$I_0$], [--], [Activities with $e_i^((0)) <= T_0$ (already completed)],
      [$I_1$], [--], [Activities with $s_i^((0)) >= T_0$ (not yet started)],
      [$E_"FS", E_"SS", E_"FF"$], [--], [Finish-to-start, start-to-start, and finish-to-finish precedence relations],
      [#pad(bottom: 5pt)[$K$]], [--], [Indices of resources $k$],
      table.hline(stroke: 0.6pt),

      // Data Parameters
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Data Parameters_]],
      [$s_i^((0))$], [days], [Baseline start time of activity $i$],
      [$delta_(i j)$], [days], [Lag or lead between activities $i$ and $j$],
      [$U_k^(max)$], [units], [Available capacity of resource $k$ per day],
      [$T_max$], [days], [Day of project deadline],
      [#pad(bottom: 5pt)[$T_0$]], [days], [Current day of project review],
      table.hline(stroke: 0.6pt),

      // Model Parameters
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Model Parameters_]],
      [$c_"late"$], [\$/day], [Late completion penalty],
      [#pad(bottom: 5pt)[$c_"early"$]], [\$/day], [Early completion bonus],
      table.hline(stroke: 0.6pt),

      // Auxiliary Variables
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Auxiliary Variables_]],
      [$d_i^((0))$], [days], [Baseline duration of activity $i$],
      [$d_i^(("crash"))$], [days], [Crash-limit duration of activity $i$],
      [$e_i^((0))$], [days], [Baseline end time of activity $i$],
      [$z_i^((0))$], [\$], [Baseline total cost of activity $i$],
      [$C_i$], [\$/day], [Crash slope of activity $i$],
      [$u_(i,k)^((0))$], [units], [Baseline daily allocation of resource $k$ on activity $i$ ($:=U_(i,k)$)],
      [$V_(i,k)$], [units/day], [Resource-draw slope of resource $k$ on activity $i$],
      [$e_i$], [days], [End time of activity $i$],
      [$z_i$], [\$], [Linearly interpolated cost of activity $i$],
      [#pad(bottom: 5pt)[$u_(i,k)$]], [units], [Linearly interpolated daily allocation of resource $k$ on activity $i$],
      table.hline(stroke: 0.6pt),

      // Decision Variables
      table.cell(colspan: 3, align: left)[#pad(top: 5pt)[_Decision Variables_]],
      [$d_i$], [days], [Duration of activity $i$],
      [$s_i$], [days], [Start time of activity $i$],

      table.footer(
        table.cell(colspan: 3, inset: 0pt, v(5pt)),
        table.hline(stroke: 1pt)
      ),
    ),
    caption: [Summary of Time--Based Model Notations],
    gap: 1em,
  ) <fig:notation-3>
  #v(1em)
]

*Project Objective.* Having @eq:crash-slope established, we can use @eq:cost-linear without ambiguity. Hence, the original single and multi--objectives of @eq:single-objective-1 and @eq:multi-objective-1 can be translated as 

$ 
min (s_(n+1), sum_(i in I) z_i (d_i)), 
$ <eq:multi-objective-3>

#noindent and 

$ 
min sum_(i in I) z_i (d_i) + c_"late" max(0, s_(n+1) - T_"max") - c_"early" max(0, T_"max" - s_(n+1)) 
$ <eq:single-objective-3>

#noindent respectively. Like the mode--based approach, here we recover a simpler linear objective. 

*Temporal Constraints.* Firstly, we maintain @eq:schedule-new as a constraint on the decision variable this time, indirectly defining the end time $e_i$ as an auxiliary variable:

$ e_i = s_i + d_i, quad forall i in I. $ <eq:end-linear>

#noindent On the other hand, we make use of @eq:duration-baseline and @eq:duration-crashed to bound our decision variable as follows:

$ d_i^(("crash")) <= d_i <= d_i^((0)), quad forall i in I. $ <eq:bound-linear>

#noindent Finally, as in the mode--based approach, the precedence relations @eq:temporal-constraint is fully preserved:

$ 
  s_j >= e_i + delta_(i j), quad forall (i,j) in E_"FS", \
  s_j >= s_i + delta_(i j), quad forall (i,j) in E_"SS", \
  e_j >= e_i + delta_(i j), quad forall (i,j) in E_"FF". 
$ <eq:temporal-linear>


*Resource Constraints.* By abstracting away the resource assignments that underlie the crashing mechanism, it becomes difficult to reintroduce resource constraints. With duration as a decision variable, one can no longer refer to a specific allocation value $x_(i,ker) U_(i,k)$. We resolve this by enforcing the linearity assumption for resource requirements as well for every resource $k in K$ in activity $i in I$. Let the baseline and crash--limiting resource requirements be

$ u_(i,k)^((0)) := U_(i,k), quad quad u_(i,k)^(("crash")) := x_max U_(i,k). $ <eq:resource-extremal>

#noindent With this, we follow the idea of @eq:crash-slope to define a resource slope as

$ 
V_(i,k) := cases(
  dfrac( u_(i,k)^(("crash")) - u_(i,k)^((0)) , d_i^((0)) - d_i^(("crash")) ) \, quad
  & "if" d_i^((0)) > d_i^(("crash")) \, ,
  0 \,
  & "if" d_i^((0)) = d_i^(("crash")),
) 
$ <eq:resource-slope>

#noindent We note that all of the above are precomputable just like the cost slope. From this, we are able to construct the resource requirement as a function of duration:

$ u_(i,k) (d_i) = V_(i,k) (d_i^((0)) - d_i) + u_(i,k)^((0)). $ <eq:resource-function>

#noindent Though this assumption that resource requirements scale linearly with duration reduction might feel contradictory to the Cobb--Douglas relationship in @eq:duration-new, it is justified by the already committed assumption that this holds for costs. Regardless, we can rewrite the resource constraint of @eq:resource-constraint as 

$ sum_(i in I) u_(i,k) (d_i) dot bb(1) \{ s_i <= s_j < e_i \} <= U_k^((max)), quad forall k in K, forall j in I. $ <eq:resource-linear>

*Crashing Constraints.* Finally, our locking mechanisms become much simpler in this linear model. For unstarted activities we have

#align(center)[
  $ #grid(
    columns: 2,
    align: (center, horizon), 
    [
      #set math.equation(numbering: none)
      $ 
        s_i >= T_0, 
      $
    ],
    [
      #set math.equation(numbering: none)
      $ quad quad forall i in I_1. $
    ]
  ) $ <eq:not-started-linear>
] 

#noindent For fully completed activities we have

#align(center)[
  $ #grid(
    columns: 2,
    align: (center, horizon), 
    [
      #set math.equation(numbering: none)
      $ 
        s_i &= s_i^(\(0\)), \
        e_i &= e_i^((0))
      $
  ],
    [
      #set math.equation(numbering: none)
      $ quad quad forall i in I_0. $
    ]
  ) $ <eq:completed-linear>
] 

#noindent At last for partially finished activities we have

#align(center)[
  $ #grid(
    columns: 2,
    align: (center, horizon), 
    [
      #set math.equation(numbering: none)
      $ 
        s_i &= s_i^(\(0\)), \
        e_i &>= T_0
      $
    ],
    [
      #set math.equation(numbering: none)
      $ quad quad forall i in I_0^C inter I_1^C. $
    ]
  ) $ <eq:started-not-completed-linear>
] 

In summary, the time--based objectives @eq:multi-objective-3 and @eq:single-objective-3, subject to constraints @eq:end-linear through @eq:started-not-completed-linear, form the optimization problem for our simplified time--based linear #sans("RC-TCTP"). Notations relevant for this specific reduction can be seen in @fig:notation-3. 

=== Optimization Method 

The linear simplification in this #sans("RC-TCTP") formulation almost makes it a pure _linear program_. However, the resource constraint @eq:resource-linear remains a non--linear complication. We can thus consider this a  The classical solution is to have either time--indexed or event--indexed binary variables so that the resource constraint can be written as knapsack inequalities at every time step or event start respectively @kone2011. In this paper, we shall take the CP--SAT approach of the mode--based model: discretize the variables and perform constraint programming. This way, we discard the need for explicitly defined binary variables and hide the multiple knapsack inequalities into a simple `cumulative` global constraint as was done previously. 

Discretization of variables is first performed using rounding and scaling tricks. Duration variables @eq:duration-baseline and @eq:duration-crashed will be rounded up to the nearest integer _without scaling_, while cost variables @eq:cost-baseline, @eq:cost-crashed will be scaled by some factor $10^(-ell)$ to maintain floating point accuracy and rounded down just as previously done. Next, we shall again borrow the interval variable notation of @laborie2009 and global constraint notation of @gccat2014. Then in this case, $d_i$ becomes the interval variable with `start`, `end`, and `size` attributes. Therefore, our linear model can be rewritten as the following constraint program: 

#[
  #set text(size: 9pt)
  $
    // Objective
    min       
    quad quad &   
    (
      s_(n+1), 
      sum_(i in I) (
        C_i dot (d_i^((0)) - #[`size`#h(0em)] (d_i)) + z_i^((0))
      )
    ), \
    
    // Constraints
    "subject to"  
    quad quad 
  
    // 1 (Duration bounds)
    &d_i^"(crash)" <= #[`size`#h(0em)] (d_i) <= d_i^((0)), 
    &forall i in I, \ 
  
    // 2 (Link start and end to interval)
    &s_i = #[`start`#h(0em)] (d_i), quad e_i = #[`end`#h(0em)] (d_i), 
    &forall i in I, \
  
    // 3 (Finish-to-Start)
    &s_j >= e_i + delta_(i j), 
    &forall (i,j) in E_"FS", \
  
    // 4 (Start-to-Start)
    &s_j >= s_i + delta_(i j), 
    &forall (i,j) in E_"SS", \
  
    // 5 (Finish-to-Finish)
    &e_j >= e_i + delta_(i j), 
    &forall (i,j) in E_"FF", \
  
    // 6 (Dynamic Resource Constraint)
    &#[`cumulative`#h(0em)] (
      #[`task`#h(0em)] ({
        d_i,
        u_(i,k)^((0)) + V_(i,k) (d_i^((0)) - #[`size`#h(0em)] (d_i))
      }), 
      U_k^"max"
    ), 
    quad quad
    &forall k in K, \
  
    // 7 (Completed Tasks)
    &s_i = s_i^((0)), quad #[`size`#h(0em)] (d_i) = d_i^((0)), 
    &forall i in I_0, \
  
    // 8 (Unstarted Tasks)
    &s_i >= T_0, 
    &forall i in I_1, \
  
    // 9 (Partially Finished Tasks)
    &s_i = s_i^((0)), quad e_i >= T_0, 
    &forall i in I_0^C inter I_1^C.
  $
]

#noindent Observe that due to the time--based formulation, we no longer need the `presence` attribute of the interval variable as well as the `exactly` global constraint. Nevertheless, we shall imitate the methodology of the mode--based model and utilize Google's CP--SAT method to solve this constraint program as efficiently as possible. 

= Experiments

We shall test our three models on a real commercial project construction dataset provided by joint work with _Integrated Decision Systems Consultancy_ (IDSC), an analytics and artificial intelligence driven business consulting firm based in Singapore @idsc. The dataset consists of $|I|$ activities (including procurement, resource mobilization, substructure, superstructure, envelope, interior, commissioning, and closeout), each of which requests a resource requirement from a set of $|K|$ resources (including wages and capacity). Furthermore, the dataset provides the baseline schedule of said activities, which is projected to be completed in $344$ days. This includes the baseline resource allocation and workhours from which the schedule is derived. As for overtime rates, we use the standard $r'_(i,k) = 1.5r_(i,k)$ for all $i in I, k in K$ as is usually enforced @hamandia2004. 

== Comparative Analysis

Our empirical analysis will involve testing each our three models on the dataset for some fixed parameter values using both the multi--objective and single--objective. With this, we will be able to compare their time--cost tradeoff, computational efficiency, also strengths and weaknesses. The time--cost tradeoff will be most visible from the pareto front generated by the multi--objective. However, a direct comparison of the generated schedule will be most visible using the single--objective, which we will visualize using a Gantt chart. Finally, we will perform sensitivity analysis on important parameters to understand its effects on the model's result. 

=== Multi--Objective Optimization 

We first simulate our three models under the time--cost multi--objective scheme. Model parameters are standardized with $alpha = beta = 0.7$, with review day $T_0 = 20$. We restate that the resource--based model is ran with the NSGA--II algorithm utilizing a serial scheduling scheme, while the mode--based and time--based model is ran with Google's CP--SAT with $epsilon$--constraints. Since the NSGA--II algorithm is stochastic, we ran the optimization $10$ times, each with a population size of $1000$, recording the mean and standard deviation of the solution. Termination is guaranteed after a maximum generation of $500$ or stagnation of less than $0.5%$ after $32$ periods. Meanwhile, under the $epsilon$--constraint method, we vary $epsilon$ between 210 and 344 days with a step size of $Delta epsilon = 4$ days. Also, the mode--based approach was ran with a discretization of $Delta := m \/ M = n \/ N = 0.1$, from which values of $M$ and $N$ can be calculated from $tau_max$ and $x_max$. 

Numerical results for this multi--objective case is in @fig:multi-objective. In particular, we assess the contribution, hypervolume, minimum achieved makespan, and minimum achieved cost. Given any specific model, its contribution counts the number of solutions it produced that lie on the pareto front, while its hypervolume is the area covered by its solutions of in the feasible region. For the latter, we calculate the hypervolume under the reference Nadir point $(344" days", \$600,000)$ and ideal point $(210" days", \$490,000)$, which safely covers all generated solutions. Note that the reported costs also only refer to _labor costs_ (devoid of bonuses or penalties). 

#[
  #set text(size: 8pt)
  #show figure: set block(breakable: true)
  #v(1.5em)
  #figure(
    table(
      columns: (auto, 1fr, 1fr, 1fr),
      inset: 10pt,
      stroke: none,
      align: horizon,
      
      // Header Row
      table.hline(stroke: 1pt),
      table.header(
        [*Metric*], 
        [*Resource-Based Model*], 
        [*Mode-Based Model*], 
        [*Time-Based Model*],
      ),
      table.hline(stroke: 1pt),
      
      [*Contribution* \ (Points / %)], 
      [$20.4 plus.minus 61.2$ \ (8.6%)], 
      [*32* \ (13.5%)], 
      [1 \ (0.4%)],
      table.hline(stroke: 0.6pt),
      
      [*Hypervolume* \ (Area / %)], 
      [$0.7922 ± 0.0048$ \ ($71.9% ± 0.4%$)], 
      [*0.8444* \ (76.6%)], 
      [0.6491 \ (58.9%)],
      table.hline(stroke: 0.6pt),
      
      [*Minimum Achieved Makespan*], 
      [$221.6 ± 1.6$ days \ (\$564.5k)], 
      [214.0 days \ (\$566.5k)], 
      [*210.0 days* \ (\$591.4k)],
      table.hline(stroke: 0.6pt),
      
      [*Minimum Achieved Cost*], 
      [\$501.6 ± 1.6k \ (302.1 days)], 
      [*\$491.5k* \ (344.0 days)], 
      [\$506.2k \ (344.0 days)],
      table.hline(stroke: 0.6pt),
      
      [*Solve Time*], 
      [$840.1 ± 64.2$ s], 
      [1006.3 s], 
      [*11.3 s*],
      table.hline(stroke: 1pt),
    ),
    caption: [Comparison of Models Under Multi--Objective.],
    gap: 1.25em,
  ) <fig:multi-objective>
  #v(1.5em)
]

The results in @fig:multi-objective show the superiority of the mode--based model in terms of optimality. It dominates in contribution and hypervolume, reaching almost 80% in both metrics. Yet this dominating performance is reflected in its heavy computational cost, requiring a solve time of over 16.5 minutes. We contrast this with the time--based model, which is unbelievably efficient, generating the entire pareto front in just 11 seconds. This averages to about 0.32 seconds per schedule. Considering its hypervolume, this tradeoff of accuracy with speed might be worthwhile in certain settings. On the other hand, the original resource--based approach is an uninteresting middle ground, seen from either hypervolume, contribution, or solve time metrics. However, an interesting observation is its greater minimum achievable cost and time compared to the other two models, suggesting that the stochastic NSGA--II algorithm might not have generated the entire feasible pareto front. 

#[
  #v(1.25em)
  #set text(size: 9pt)
  #figure(
    image("src/Pareto.svg", width: 66%),
    caption: [Pareto Fronts of All Three Models $(alpha = beta = 0.7)$],
  ) <fig:pareto>
  #v(1em)
]   

As a time--cost multi--objective is 2--dimensional, we shall be able to further visualize the pareto front as in @fig:pareto. The visual confirms the superiority of the mode--based model to optimize the best schedules within any deadline. On the other hand, the resource--based model struggles to capture the entire pareto front. One explanation might be that the NSGA--II algorithm only obtained candidate schedules with completion times greater than \~290 days that are strictly dominated by the schedule with \~290 days. This hints at the difficulty to randomly evolve a schedule towards optimality at those completion times, which might be because they require only very minimal changes in overtime and overmanning, which evolutionary mechanism cannot capture (unlike exact methods). Finally, we notice as well that the time--based model, despite being computationally cheap, is fully dominated by both mode and resource--based model. 

However, we do note that since these three approaches differ fundamentally in the _model_, not just the algorithmic _method_, these optimality comparisons should not be taken at face value. Instead, we also consider the possibility that a model over or underestimates certain values due to modelling choices. The mode--based model is the most direct discretization of the resource--based model, akin to estimating integrals with sums. Therefore, its modelling disagreements are minimal, and any differences in pareto fronts is likely due to algorithmic choice. This further highlights the true dominance of the CP--SAT technique for the discretized mode--based MILP formulation. In contrast, the time--based model is a fundamentally different reduction of the resource--based model, shifting towards time reductions from resource allocation. The linearity assumption severely abstracts away the underlying mechanisms of crashing, which causes overestimation of crashing costs. Regardless, the extremely quick solve time justifies this simplification in many settings where accuracy is not as valued. 

#[
  #v(1.25em)
  #set text(size: 9pt)
  #figure(  
    image("src/Total Cost.svg", width: 66%),
    caption: [Total Cost of All Three Models.],
  ) <fig:total-cost>
  #v(1em)
]

We also further consider the additional scenario of adding a daily bonus $c_"early" = \$2000$ and penalty $c_"late" = \$5000$ over these optimized pareto fronts with deadline $T_max = 250$. This yields @fig:total-cost. Recall that the optimization was done _without_ consideration of these bonuses and penalties. We observe first that the bonuses cover the rise in costs for shorter completion times. One thus hypothesizes that bonuses and penalties might incentivize more extreme crashing if incorporated to the optimization, which we will study further in the scalarized scheme of Section 3.1.2. Then, we also notice that the penalties severely punish late schedules. This properly models the indirect costs associated with theoretical time--cost tradeoffs. 

=== Single--Objective Optimization 

Next, we provide numerical results for all three models under the bonus--penalty based single--objective. Recall this acts as a scalarization of the time--cost tradeoff. The parameters used in all three models are similar to before: $T_0 = 20, T_max = 250, alpha = beta = 0.7, c_"early" = \$2000, c_"late" = \$5000$. The implemented genetic algorithm utilizes a population size of $1000$ with termination conditions similar to that of the multi--objective case. Running the optimization under these familiar settings, we obtain the results in @fig:single-objective. 

#pagebreak()

#[
  #set text(size: 8pt)
  // #v(1.5em)
  #show figure: set block(breakable: true)
  #figure(
    table(
      columns: (auto, 1fr, 1fr, 1fr),
      stroke: none,
      inset: 10pt,
      table.hline(stroke: 1pt),
      align: horizon,table.header(
        [*Metric*], [*Resource--Based*], [*Mode--Based*], [*Time--Based*],
      ),
      
      table.hline(stroke: 1pt),
      [Optimal Makespan $(s_(n+1))$ ], 
      [217.14 $plus.minus$ 0.65 days], 
      [220.33 days], 
      [*213.00 days*],
      table.hline(stroke: 0.6pt),
      
      [Rescue Margin \ $(T_"base" - s_(n+1))$], 
      [126.86 $plus.minus$ 0.65 days], 
      [123.67 days], 
      [*131.00 days*],
      table.hline(stroke: 0.6pt),
      
      [Target Margin \ ($T_max - s_(n+1)$)], 
      [32.86 $plus.minus$ 0.65 days], 
      [29.7 days], [*37.0 days*],
      table.hline(stroke: 0.6pt),
      
      [Labor Cost $(sum_(i in I) z_i)$], 
      [\$561,967.72 \ $plus.minus$ \$1,072.31], 
      [*\$553,426.94*], 
      [\$584,970.19],
      table.hline(stroke: 0.6pt),
      
      [Penalty $(c_"late" max{0, s_(n+1) - T_"max"})$], [\$0.00], [\$0.00], [\$0.00],
      table.hline(stroke: 0.6pt),
      
      [Bonus $(c_"early" max{0, T_"max" - s_(n+1)})$], [\$65,711.31 \ $plus.minus$ \$1,298.80], 
      [\$59,340.00], 
      [*\$74,000.00*],
      table.hline(stroke: 0.6pt),
      
      [Total Cost], 
      [\$496,256.41 \ $plus.minus$ \$1,094.68], 
      [*\$494,086.94*], 
      [\$510,970.19],
      table.hline(stroke: 0.6pt),
      
      [Solve Time], 
      [1275.8 $plus.minus$ 6.9 s], 
      [301.2 s], 
      [*2.16 s*],
      table.hline(stroke: 1pt),
    ),
    caption: [Comparison of Models Under Single--Objective (Bonus--Penalty).],
    gap: 1.5em,
  ) <fig:single-objective>
  #v(1.5em)
]

From @fig:single-objective, we conclude that the time--based model seems to provide the most extreme crashing solutions compared to the other two model. This is unlike the multi--objective case, where given a fixed cost, the time--based model usually offers the most conservative schedule. With this, also considering its attained bonus value, the incorporation of the bonuses and penalties presumably most affects the time--based model. Nevertheless, the most optimal solution in terms of minimizing total cost is achieved by the mode--based model, just as in the multi--objective scenario. Offering the mildest crashing option of the three models, it balance bonuses and labor costs effectively. Finally, we consider the computational costs of the three models. Unlike the multi--objective case, the resource--based model is now most severely demanding. This might be because the NSGA--II algorithm is heavily optimized in the multi--objective setting with parallelization and clever sorting, unlike the manual $epsilon$--constraints implemented for CP--SAT. However, in the single--objective case, stochastic genetic algorithms are indeed generally slower than CP--SAT, as is evidenced here. We also highlight that the time--based model remains the most computationally cheap model. With an attained cost and completion day not wildly different from the best mode--based model, we see that the simplification is a worthwhile sacrifice for computational efficiency. 

In this single--objective scheme, we obtain a single optimized schedule for the three models. With this, we visualize the three models as a Gantt chart in @fig:model-A-sched, @fig:model-B-sched, and @fig:model-C-sched. Activities colored in red are the ones selected to be crashed by the model. Recognizing the continuous nature of the resource--based model, we shall arbitrarily consider an activity "crashed" if either both overmanning multipliers and overtime addends or the duration reduction exceed $delta = 0.05$. We also visualize the baseline schedule in the background of the three Gantt charts for comparison. 

#place(auto, float: true)[
  #rotate(-90deg, reflow: true)[
    #figure(
      image("src/Model A.svg", width: 100%), 
      caption: [Resource--Based Model ($alpha = beta = 0.7, c_"early" = \$2000, c_"late" = \$5000$)],
    ) <fig:model-A-sched>
  ]
]

#place(auto, float: true)[
  #rotate(-90deg, reflow: true)[
    #figure(
      image("src/Model B.svg", width: 100%),
      caption: [Mode--Based Model ($alpha = beta = 0.7, c_"early" = \$2000, c_"late" = \$5000$)],
    ) <fig:model-B-sched>
  ]
]

#place(auto, float: true)[
  #rotate(-90deg, reflow: true)[
    #figure(
      image("src/Model C.svg", width: 100%),
      caption: [Time--Based Model ($alpha = beta = 0.7, c_"early" = \$2000, c_"late" = \$5000$)],
    ) <fig:model-C-sched>
  ]
]


By visual observation of these charts, we notice that some tasks that are preferably and unanimously crashed among all three optimized schedules, while some activities are rarely crashed in any model. These preferred activities might be ones that lie in a _critical path_ and are major bottlenecks for the construction, which our three models identify as most worthwhile to crash. Hence, we see that our model simulates the selective nature of critical path approaches indirectly. This emergent behavior is extremely valuable, as it shows our model provides actionable solutions. This is not the case if our model provides solutions that crash every single activity only incrementally to achieve the same completion time. Observe as well that some reordering of tasks were done, which shows the power of well--defined precedence relations in project scheduling problems. 

== Sensitivity Analysis

Next, we perform sensitivity analysis on key model parameters. In particular, we shall test sensitivity only on the original resource--based model utilizing the genetic algorithm approach, as the other two are model simplifications that should yield similar results according to the obtained results of Section 3.1. We shall test the affect of the Cobb--Douglas elasticities $alpha$ and $beta$, the bonus--penalty parameters $c_"early"$ and $c_"late"$, as well as the project deadline $T_max$. We stress the standardized usage of model parameters $T_0 = 20, T_max = 250, alpha = beta = 0.7, c_"early" = \$2000, c_"late" = \$5000$ in all preceding results whenever a parameter is not being wiggled. Unless otherwise mentioned, the genetic algorithm also utilizes a population size of $1000$, with termination after a maximum generation of $500$ or stagnation of less than $0.5%$ after $32$ periods. 

=== Cobb--Douglas Elasticities  

Here, we first consider the one--factor affect of the labor elasticity $alpha$, representing overcrowding factors, on the crashing solution generated. To do so, we ran the genetic algorithm for the resource--based model under various values of $alpha$, obtaining the total costs and completion days for each under the single--objective scheme. Similarly, the one--factor impact of capital elasticity $beta$, representing overtime factors, is obtained in the same way. We used a population size of $1000$. This results in the plot of @fig:oat-alpha-beta. 

#[
  #v(1.25em)
  #set text(size: 8pt)
  #figure(  
    grid(
      columns: 2,
      image("src/sensitivity/oat_alpha.svg"),
      image("src/sensitivity/oat_beta.svg")
    ),
    caption: [One--Factor Sensitivity of $alpha$ and $beta$ (Single--Objective).],
  ) <fig:oat-alpha-beta>
  #v(0.75em)
]

@fig:oat-alpha-beta shows the obvious negative relationship between both overmanning and overtime with total cost and optimal makespan. In fact, the crashing solutions seem to be equally sensitive to both $alpha$ and $beta$, showing their independence. Notice further that whenever $alpha < 0.3$ or $beta < 0.3$, the provided schedule is _late_ (over the $T_max = 250$ days deadline). This perfectly captures the inability to accelerate a project given extreme inefficiencies in the workforce. Most remarkably, despite the Cobb--Douglas utility being inherently non--linear in $alpha$ and $beta$ relative to each individual activity, the aggregation across the entire schedule exhibits a rather linear relationship with these elasticity parameters when the other is held constant. The observation holds for both total cost and optimal makespan, such that by transitivity both of these are approximately linearly related. This might explain why the time--based model offered similar solutions to the resource or mode--based model despite severe linearity simplifications, as the above reasoning holds for fixed $alpha$ and $beta$ during precomputation. 

#[
  #v(1.25em)
  #set text(size: 9pt)
  #figure(  
    image("src/sensitivity/tat_alpha_beta_2panel.svg"),
    caption: [Two--Factor Sensitivity of $(alpha, beta)$ (Single--Objective).],
  ) <fig:tat-alpha-beta>
  #v(0.75em)
]

To understand elasticity parameters further, we plot as a heat map in @fig:tat-alpha-beta the simultaneous effects of $(alpha,beta)$ on the total cost and optimal makespan of the crashed schedule. Here, the almost linear relationship between $alpha$ and $beta$ with cost and time is challenged. In particular, we consider the contour lines generated. Notice that they form non--straight curves and are more densely packed at lower values of $alpha$ and $beta$. Thus, while holding one parameter fixed yields an approximate linearity, varying both simultaneously reveals the true underlying nonlinearity of the Cobb--Douglas model. Therefore, one hypothesizes that the time--based model might perform poorly in scenarios where $alpha$ and $beta$ vary throughout the project. 

#[
  #v(1.25em)
  #set text(size: 8pt)
  #figure(  
    grid(
      columns: 2,
      image("src/sensitivity/pareto_shift_alpha.svg"),
      image("src/sensitivity/pareto_shift_beta.svg")
    ),
    caption: [One--Factor Sensitivity of $alpha$ and $beta$ (Multi--Objective).],
  ) <fig:oat-alpha-beta-multi>
  #v(0.75em)
]

We also interest ourselves in the role of $alpha$ and $beta$ in the multi--objective scenario. @fig:oat-alpha-beta-multi gives the pareto fronts generated for various different values of $alpha$ and $beta$ with the other held constant at its default. Both plots confirm the inverse relationship between time--cost and both elasticity parameters. However, we also see glaring differences between $alpha$ and $beta$. Here, lower overcrowding inefficiency yields shorter pareto fronts, as both the best and worst crashing solutions become better in general. On the other hand, lower overtime inefficiencies generally make the pareto fronts longer. That is, even if the pareto front is positively shifted downwards for lower values of $beta$, the genetic algorithm finds more extreme Nadir points makespan wise. Furthermore, we see that the pareto fronts only minimally change for makespans of greater than $260$ days or costs less than \$520,000, despite the changes in $beta$. Therefore, the multi--objective case paints a clearer picture on the varying role of $alpha$ and $beta$. 

=== Bonus--Penalty Parameters

Next, we analyze the affect of daily bonus and penalty rates that scalarize the multi--objective. We note that they act as soft constraints for project completion, so the sensitivity of a crashing solution with respect to these parameters are very important. Here, we again ran the genetic algorithm of the resource--based model across various values of $c_"early"$ and $c_"late"$ to obtain the total cost and optimal makespan under those conditions. The results are visualized in @fig:oat-penalty-bonus. 

#[
  #v(1.5em)
  #set text(size: 8pt)
  #figure(  
    grid(
      columns: 2,
      image("src/sensitivity/oat_c_early.svg"),
      image("src/sensitivity/oat_c_late.svg")
    ),
    caption: [One--Factor Sensitivity of $c_"late"$ and $c_"early"$ (Single--Objective).],
  ) <fig:oat-penalty-bonus>
]

#[
  #set text(size: 9pt)
  #figure(  
    image("src/sensitivity/tat_c_early_c_late_2panel.svg", width: 100%),
    caption: [Two--Factor Sensitivity of $(c_"late", c_"early")$ (Single--Objective).],
    placement: bottom,
  ) <fig:tat-c-early-c-late>
  #v(0.5em)
]

@fig:oat-penalty-bonus show interesting implications regarding the scalarization choice through bonuses and penalties. We note that greater early bonuses drastically decrease total project costs and completion times, as it incentives more extreme crashing solutions. On the other hand, the penalty parameter exhibit a more complex relationship. Recall that penalties act as a soft constraint for the optimization problem to generate on--time schedules. This becomes apparent for values of $c_"late" > \$1000$ as it functions as an artificial Big--$M$ variable, where the obtained schedules settle at a much lower total cost by having earlier unpunished makespans. Thus, the range $c_"late" in (0,1000)$ becomes a critical region where the tradeoffs between increasing labor costs due to crashing and penalties due to tardiness becomes most convoluted. 

We again visualize the fwo--factor influence of both penalty and cost on the single--objective model with heatmaps as in @fig:tat-c-early-c-late. Here, the non--triviality of the $c_"late" in (0,1000)$ region becomes more obvious, where we see the densely packed contour lines that show the substantial impact of penalties to the crashing solution. The influence of bonuses remain gradual but clear, incentivizing crashed schedules that complete much earlier. 

=== Project Deadline

Finally, we consider the model's behavior under various project deadlines, which stress tests the model's crashing ability. As usual, we vary the values of $T_max$ for the resource--based model, recording the total cost and optimal makespan obtained. The result is plotted in @fig:oat-T-max.

#[
  #v(1.25em)
  #set text(size: 9pt)
  #figure(  
    image("src/sensitivity/oat_T_max.svg", width: 66%),
    caption: [One--Factor Sensitivity of $T_max$ (Single--Objective).],
  ) <fig:oat-T-max>
  #v(1em)
]

We find two surprising relationships in @fig:oat-T-max. First, total project cost is almost perfectly linearly related to the target deadline. This further corroborates the time--based model's assumption of linearity. However, second, this total cost is achieved through a non--linear crashing strategy. We see that the Cobb--Douglas model provides a crashing solution that always meets every target deadline. Yet the optimal makespan obtained

= Conclusion

= Bibliography

#bibliography("ref.bib", title: none, style: "ieee")