#import "ppt_template.typ" : *
#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge
#import "@preview/cetz:0.5.2"

#let sans(content) = text(font: "New Computer Modern Sans", content)
#let nonumeq = math.equation.with(block: true, numbering: none)
#let dm(x) = box[#nonumeq[#x]]
#let dfrac(x,y) = math.frac(dm(x),dm(y))

#let square(color: none, nudge: false, body) = box(
  stroke: if color != none { 0.5pt + color } else { 0.5pt },
  inset: 4pt,
  fill: color,
  baseline: if nudge {0.05em} else {0em},
  body
)

#set par(justify: true)

#set enum(indent: 1em, body-indent: 1em)

#show: setup.with(
  ratio: "16-9",
  primary: rgb("005aab"),
  title: [A Cobb–Douglas Approach to Resource--Constrained Time–Cost Tradeoff Problems in Project Crashing],
  subtitle: [Industrial Mathematics Week],
  date: "13 July, 2026",
  author: "Timothy Niels Ruslim",
  institute: "Institut Teknologi Bandung"
)

#titlepage()

// ========== Table of Contents ==========

#content(title: "Table of Contents")

// ========== Introduction ==========

#section(title: "Introduction")

#slide(title: "Project Crashing & RCPSPs")[
  #set par(justify: false)

  *Project crashing* is a schedule compression technique to meet late deadlines, creating an economic *time--cost tradeoff* @caglayan2024.

  #v(0.5em)
  *Resource-Constrained Project Scheduling Problems* (RCPSPs) are the de-facto model for real-world scheduling @Artigues2026:

  / Project: graph $(I, cal(E))$ of activities $i in I$ with precedence $cal(E)$
  / Resources: set $cal(K)$ with capacity $R_k$; requirement $r_(i,k)$
  / Schedule: start times $s_i$ and end times $e_i$ satisfying feasibility
  / Objective: minimize $cal(G)(s_(n+1))$

  #v(0.5em)
  #my-block(title: "Key Challenge")[
    RCPSPs are *NP-hard* @blazewicz1983 due to resource constraints, making optimization method selection essential.
  ]
]

#slide(title: "Problem Classification")[
  #set par(justify: false)

  *Brucker's $alpha | beta | gamma$ notation* @Brucker1999 classifies RCPSPs by:

  / $alpha$: Resource environment (renewable, non-renewable)
  / $beta$: Activity characteristics (prec, temp, ...)
  / $gamma$: Objective function (makespan, time-cost tradeoff, ...)

  #v(0.5em)
  *Three approaches to decision variables:*

  #text(size: 13pt)[
    + *Time-based:* direct schedule control (duration, binary indicators) @kelley1961
    + *Mode-based:* binary selection of execution "modes" (#sans("MRCPSP")) @Brucker1999
    + *Resource-based:* direct resource allotment (#sans("RIP")/#sans("RACP")) @Hartmann2022
  ]

  #v(0.5em)
  The choice of decision variables determines the objective $gamma$, and is one of the most important aspects of RCPSPs.
]

#slide(title: "Time--Cost Tradeoff Problems")[
  #set par(justify: false)

  *Resource-constrained Time--Cost Tradeoff Problems* (RC-TCTPs) reduce project costs while minimizing makespan @Hosseinpour2023.

  / Direct costs: labor, materials
  / Indirect costs: leaseholds, penalties, overheads

  #v(0.4em)
  #align(center)[
    #cetz.canvas({
      import cetz.draw: *

      let pts-indirect = range(15, 56).map(i => {
        let x = i / 10.0
        (x, 0.5 * (x - 3.0) + 2.0)
      })

      let pts-direct = range(15, 56).map(i => {
        let x = i / 10.0
        (x, 3.125 / (x - 0.5) + 0.75)
      })

      let pts-total = range(17, 55).map(i => {
        let x = i / 10.0
        (x, (0.5 * (x - 3.0) + 2.0) + (3.125 / (x - 0.5) + 0.75))
      })

      line((0, 0), (6.5, 0), mark: (end: ">"), stroke: 0.6pt)
      line((0, 0), (0, 5.5), mark: (end: ">"), stroke: 0.6pt)
      content((6.65, 0), text(size:9pt)[Time], anchor: "west")
      content((0, 5.65), text(size:9pt)[Cost], anchor: "south")

      line(..pts-indirect, stroke: (paint: black, thickness: 0.5pt, dash: "dashed"))
      line(..pts-direct, stroke: (paint: black, thickness: 0.5pt, dash: "dashed"))
      line(..pts-total, stroke: (paint: black, thickness: 0.8pt))

      line((3.0, 0), (3.0, 4.0), stroke: (paint: black, thickness: 0.4pt, dash: "dotted"))

      line((1.5, 0.1), (1.5, -0.1), stroke: 0.5pt)
      content((1.5, -0.35), text(size:9pt)[$D_c$], anchor: "north")

      line((5.5, 0.1), (5.5, -0.1), stroke: 0.5pt)
      content((5.5, -0.35), text(size:9pt)[$D_n$], anchor: "north")

      line((0.1, 1.25), (-0.1, 1.25), stroke: 0.5pt)
      content((-0.3, 1.25), text(size:9pt)[$C_c$], anchor: "east")

      line((0.1, 3.875), (-0.1, 3.875), stroke: 0.5pt)
      content((-0.3, 3.875), text(size:9pt)[$C_n$], anchor: "east")

      content((5.55, 4.7), text(size:9pt)[Total Cost], anchor: "west")
      content((5.675, 3.35), text(size:9pt)[Indirect Cost], anchor: "west")
      content((5.65, 1.375), text(size:9pt)[Direct Cost], anchor: "west")
    })
  ]

  #align(center)[The interplay of cost types yields a nontrivial tradeoff. TCTPs often employ *multi-objective* functions or scalarizations @Agarwal2013.]
]

#slide(title: "Optimization Methods")[
  #set par(justify: false)

  *Exact Methods:*
  + *Mixed-Integer Linear Programming* (MILP) --- best for mode-based decisions
  + *Constraint Programming* (CP) --- more flexible, interval variables @laborie2009
  + *Branch and Bound* (B&B) --- widely applicable to MILP and CP
  + *CP-SAT / SAT solvers* --- state-of-the-art results @Artigues2026

  #v(0.5em)
  *Non-Exact Methods:*
  + *Genetic Algorithms* (GA) --- most notable metaheuristic @hartmann1998
  + *Particle Swarm* (PSO) and *Ant Colony* (ACO) @merkle2002 @zhang2005
  + *Machine Learning* --- promising but computationally expensive

  #v(0.5em)
  #my-block(title: "Our Approach")[
    We employ *GA* (NSGA-II) for the non-linear model and *CP-SAT* for the linearized/discretized models.
  ]
]

// ========== Models ==========

#section(title: "Models")

#slide(title: "Models Overview")[
  #set align(center + horizon)

  #v(0.5em)
  #diagram(
    spacing: (1em, 1em),
    node((0, 0), [*Resource-Based* \
      #text(size: 12pt)[Cobb-Douglas · MINLP] \
      #text(size: 12pt)[GA / NSGA-II]], fill: rgb("005aab").lighten(80%), stroke: rgb("005aab")),
    node((-3.2, -2.2), [*Mode-Based* \
      #text(size: 12pt)[Discretized MILP] \
      #text(size: 12pt)[CP-SAT]], fill: rgb("005aab").lighten(80%), stroke: rgb("005aab")),
    node((3.2, -2.2), [*Time-Based* \
      #text(size: 12pt)[Linear Interpolation] \
      #text(size: 12pt)[CP-SAT]], fill: rgb("005aab").lighten(80%), stroke: rgb("005aab")),
    edge((0, 0), (-3.2, -2.2), [Discretize \
      modes]),
    edge((0, 0), (3.2, -2.2), [Linearize \
      crash slope]),
  )

  #v(1.5em)
  Three formulations of increasing simplification, all exploiting the *Cobb-Douglas production function*:

  $
    Y(L, K) = A L^alpha K^beta
  $

  where $alpha$ and $beta$ are labor and capital elasticity @cobb1928. We build on Shen et al. @shen2016 who applied Cobb-Douglas to project crashing with crew labor and equipment.
]

#slide(title: "Resource-Based: Baseline Setup")[
  #set par(justify: false)

  Given a baseline schedule with activities $I$ and resources $K$:

  #grid(
    columns: (1fr, 1fr),
    column-gutter: 1.2em,
    [
      *Baseline effective duration* (8 hours/day):

      $
        d_(i,k)^((0)) := (W_(i,k)^((0))) / (8 U_(i,k))
      $

      *Baseline schedule:*

      $
        d_i^((0)) := max_(k in K) d_(i,k)^((0)), quad e_i^((0)) = s_i + d_i^((0))
      $
    ],
    [
      *Baseline cost:*

      $
        z_(i,k)^((0)) := d_(i,k)^((0)) dot U_(i,k) dot 8 dot r_k = W_(i,k)^((0)) dot r_k
      $

      #v(0.5em)
      #text(size: 13pt)[
        / $W_(i,k)^((0))$: baseline work effort (unit-hours)
        / $U_(i,k)$: baseline daily allocation (units)
        / $r_k$: hourly wage (\$/hour)
      ]
    ],
  )
]

#slide(title: "Resource-Based: Crashing Formulas")[
  #set par(justify: false)

  Two crashing strategies: *overmanning* ($x_(i,k)$) and *overtime* ($tau_(i,k)$).

  #grid(
    columns: (1fr, 1fr),
    column-gutter: 1.2em,
    [
      *Naive duration:*
      $
        d_(i,k) = (W_(i,k)) / ((8 + tau_(i,k))(x_(i,k) U_(i,k)))
      $
      Implies $z_(i,k) = z_(i,k)^((0))$ (no extra cost) --- unrealistic!

      #v(0.3em)
      *Cobb-Douglas duration* with $A_(i,k) = U_(i,k)^(1-alpha) 8^(1-beta)$:

      $
        d_(i,k) = underbrace(W_(i,k) / (8 U_(i,k)), d_(i,k)^((0))) dot underbrace((1 / x_(i,k))^alpha, "overcrowd") dot underbrace((8 / (8 + tau_(i,k)))^beta, "overwork")
      $
    ],
    [
      *Expanded cost:*

      $
        z_(i,k) = underbrace(W_(i,k) r_k, z_(i,k)^((0))) dot underbrace(x_(i,k)^(1-alpha), "overcrowd") dot underbrace(((8 + tau_(i,k)) / 8)^(1-beta), "overwork") dot underbrace((8 + r'_k / r_k tau_(i,k)) / (8 + tau_(i,k)), "extra wage")
      $

      #v(0.3em)
      #text(size: 12pt)[
        The Cobb-Douglas approach captures *inefficiencies* in overmanning and overtime crashing:
        / "overcrowd": diminishing returns from extra workers
        / "overwork": diminishing returns from extra hours
        / "extra wage": overtime premium $r'_k >= r_k$
      ]
    ],
  )
]

#slide(title: "Resource-Based: Constraints & Objectives")[
  #set par(justify: false)

  #grid(
    columns: (1fr, 1fr),
    column-gutter: 1.2em,
    [
      #text(size: 12pt)[
        *Temporal:* $ s_j >= e_i + delta_(i j), quad forall (i,j) in E_"FS" $ (and SS, FF)

        *Duration bound:* $ d_(i,k) >= gamma dot d_(i,k)^((0)) $

        *Resource:* $ sum_(i in I) x_(i,k) U_(i,k) dot bb(1) \{s_i <= s_j < s_i + d_(i,k)\} <= U_k^(max) $

        *Crashing:* 3 task types --- unstarted ($I_1$), completed ($I_0$), partial ($I_0^C inter I_1^C$)
      ]
    ],
    [
      *Multi-objective:*
      $
        min (s_(n+1), sum_(i in I) sum_(k in K) z_(i,k)(x_(i,k), tau_(i,k)))
      $

      *Single-objective* (bonus-penalty):
      $
        min sum_(i in I) sum_(k in K) z_(i,k) + c_"late" max(0, s_(n+1) - T_"max") - c_"early" max(0, T_"max" - s_(n+1))
      $

      #text(size: 12pt)[Decision variables: $s_i$, $x_(i,k)$, $tau_(i,k)$. This is a *MINLP*.]
    ],
  )
]

#slide(title: "Resource-Based: NSGA-II Genetic Algorithm")[
  #set par(justify: false)

  The non-linearity motivates a *metaheuristic* approach --- Genetic Algorithm (GA) @hartmann1998.

  #v(0.3em)
  *Chromosome structure* ($2|I|dot|K| + |I|$ genes):

  / Genes $1$ to $|I|dot|K|$: overmanning multipliers $x_(i,k)$
  / Genes $|I|dot|K|+1$ to $2|I|dot|K|$: overtime addends $tau_(i,k)$
  / Remaining genes: activity order priority $in [0,1]$

  #v(0.3em)
  *Evolution:*
  + Uniform initialization between bounds
  + Tournament selection
  + Simulated binary crossover (SBX)
  + Polynomial mutation
  + Implemented in `pymoo` (Python)

  #v(0.3em)
  *Serial Scheduling Scheme:* Build schedule from priority order, push start times forward, shift on resource conflicts. Cost acts as fitness score. Generalizes to multi-objective via *NSGA-II*.
]

#slide(title: "Mode-Based: Discretization & MILP")[
  #set par(justify: false)

  Partition overmanning $[1, x_max]$ into $M$ intervals and overtime $[0, tau_max]$ into $N$ intervals:

  $
    x_(i,k)^((m)) = 1 + m/M (x_max - 1), quad tau_(i,k)^((n)) = n/N tau_max
  $

  Each pair $(m,n) in cal(M)$ is a *mode* with *precomputed* duration and cost:

  #grid(
    columns: (1fr, 1fr),
    column-gutter: 1.2em,
    [
      $
        d_(i,k)^((m,n)) = d_(i,k)^((0)) dot (1 / x_(i,k)^((m)))^alpha dot (8 / (8 + tau_(i,k)^((n))))^beta
      $

      $
        z_(i,k)^((m,n)) = z_(i,k)^((0)) dot (x_(i,k)^((m)))^(1-alpha) dot ((8 + tau_(i,k)^((n))) / 8)^(1-beta) dot (8 + r'_k / r_k tau_(i,k)^((n))) / (8 + tau_(i,k)^((n)))
      $
    ],
    [
      *Decision variable:* $xi_(i,k)^((m,n)) in {0,1}$ (mode selector)

      #v(0.3em)
      #text(size: 12pt)[
        *Uniqueness:* $sum_((m,n) in cal(M)) xi_(i,k)^((m,n)) = 1$

        *Objective* (linearized):

        $min (s_(n+1), sum_(i,k) sum_((m,n)) z_(i,k)^((m,n)) xi_(i,k)^((m,n)))$

        This is a *Mixed-Integer Linear Program* (MILP).
      ]
    ],
  )
]

#slide(title: "Mode-Based: CP-SAT Formulation")[
  #set par(justify: false)

  Reformulate using *interval variables* @laborie2009 with `start`, `end`, `size`, `presence` attributes, and `cumulative` / `exactly` *global constraints* @gccat2014.

  #grid(
    columns: (1fr, 1fr),
    column-gutter: 1em,
    [
      #text(size: 8pt)[
        $
          min quad & (s_(n+1), sum_(i in I) sum_(k in K) sum_((m,n)) z_(i,k)^((m,n)) dot "pres"(xi_(i,k)^((m,n)))) \
          "s.t." quad & "exactly"(1, {"pres"(xi_(i,k)^((m,n)))}, 1), forall i, k, \
          & "size"(xi_(i,k)^((m,n))) = d_(i,k)^((m,n)), \
          & "pres"(xi) = 1 arrow.l.r "start"(xi) = s_i, \
          & e_i = max_(k in K) sum_((m,n)) "pres"(xi) dot "end"(xi),
        $
      ]
    ],
    [
      #text(size: 8pt)[
        $
          quad & s_j >= e_i + delta_(i j), forall (i,j) in E_"FS", \
          quad & "cumulative"("task"({xi, x_(i,k)^((m)) U_(i,k)}), U_k^"max"), forall k, \
          quad & "pres"(xi_(i,k)^((0,0))) = 1, s_i = s_i^((0)), forall i in I_0, \
          quad & s_i >= T_0, forall i in I_1, \
          quad & s_i = s_i^((0)), forall i in I_0^C inter I_1^C.
        $
      ]
    ],
  )

  #v(0.2em)
  #text(size: 11pt)[
    Solved via *CP-SAT* (Google) --- hybrid of CP propagation and SAT conflict-driven clause learning (LCG) @krupke2026. Integer domains via scaling/rounding: $d^(m,n) = ceil(10^(ell_1) dot ...)$, $z^(m,n) = floor(10^(ell_2) dot ...)$.
  ]
]

#slide(title: "Time-Based: Linear Formulation & CP-SAT")[
  #set par(justify: false)

  Assume *direct costs are linearly related* to duration reduction:

  #grid(
    columns: (1fr, 1fr),
    column-gutter: 1.2em,
    [
      *Linear cost:*
      $
        z_i(d_i) = C_i (d_i^((0)) - d_i) + z_i^((0))
      $

      *Crash slope* from Cobb-Douglas extremal values:
      $
        C_i = cases(dfrac(z_i^("crash") - z_i^((0)), d_i^((0)) - d_i^("crash")) & "if" d_i^((0)) > d_i^("crash"), 0 & "if" d_i^((0)) = d_i^("crash"))
      $

      *Resource slope* (same idea):
      $
        V_(i,k) = (u_(i,k)^("crash") - u_(i,k)^((0))) / (d_i^((0)) - d_i^("crash"))
      $
    ],
    [
      *CP-SAT program:*

      #text(size: 10pt)[
        $
          min quad & (s_(n+1), sum_(i in I) C_i (d_i^((0)) - "size"(d_i)) + z_i^((0))) \
          "s.t." quad & d_i^"crash" <= "size"(d_i) <= d_i^((0)), \
          quad & s_i = "start"(d_i), quad e_i = "end"(d_i) \
          quad & s_j >= e_i + delta_(i j), forall (i,j) in E_"FS" \
          quad & "cumulative"("task"({d_i, u_(i,k)^((0)) + V_(i,k)(d_i^((0)) - "size"(d_i))}), U_k^"max"), forall k \
          quad & s_i = s_i^((0)), "size"(d_i) = d_i^((0)), forall i in I_0
        $
      ]
    ],
  )
]

// ========== Experiments ==========

#section(title: "Experiments")

#slide(title: "Dataset")[
  #set par(justify: false)

  Real commercial project construction dataset from *Integrated Decision Systems Consultancy* (IDSC), Singapore @idsc.

  #v(0.5em)
  / Activities: $|I|$ activities (procurement, substructure, superstructure, envelope, interior, commissioning, closeout)
  / Resources: $|K|$ resources with wages $r_k$ and capacity $U_k^(max)$
  / Baseline: 344 days projected completion
  / Overtime: $r'_k = 1.5 r_k$ (standard) @hamandia2004

  #v(0.5em)
  *Standardized parameters:*

  $alpha = beta = 0.7$, $T_0 = 20$, $T_max = 250$, $c_"early" = \$2000$/day, $c_"late" = \$5000$/day

  #v(0.3em)
  *Methods:*
  + Resource-Based: NSGA-II (population 1000, max gen 500)
  + Mode-Based: CP-SAT with $epsilon$-constraints ($Delta epsilon = 4$ days, $Delta = 0.1$)
  + Time-Based: CP-SAT with $epsilon$-constraints
]

#slide(title: "Multi-Objective Results")[
  #set par(justify: false)

  #text(size: 9pt)[
    #align(center)[
      #table(
        columns: (auto, 1fr, 1fr, 1fr),
        inset: 6pt,
        stroke: none,
        align: horizon,

        table.hline(stroke: 1pt),
        table.header(
          [*Metric*], [*Resource-Based*], [*Mode-Based*], [*Time-Based*],
        ),
        table.hline(stroke: 1pt),

        [*Contribution* \ (% of Pareto)], [8.6%], [*13.5%*], [0.4%],
        table.hline(stroke: 0.6pt),

        [*Hypervolume*], [71.9% $plus.minus$ 0.4%], [*76.6%*], [58.9%],
        table.hline(stroke: 0.6pt),

        [*Min Makespan*], [221.6 $plus.minus$ 1.6 d (\$564.5k)], [214.0 d (\$566.5k)], [*210.0 d (\$591.4k)*],
        table.hline(stroke: 0.6pt),

        [*Min Cost*], [\$501.6k $plus.minus$ 1.6k (302.1 d)], [*\$491.5k* (344.0 d)], [\$506.2k (344.0 d)],
        table.hline(stroke: 0.6pt),

        [*Solve Time*], [840.1 $plus.minus$ 64.2 s], [1006.3 s], [*11.3 s*],
        table.hline(stroke: 1pt),
      )
    ]
  ]

  #v(0.3em)
  #my-block(title: "Key Findings")[
    *Mode-Based* dominates optimality (76.6% hypervolume). *Time-Based* is unbelievably fast (11.3s for entire Pareto front --- 0.32s/schedule). Resource-Based is an uninteresting middle ground.
  ]
]

#slide(title: "Pareto Fronts & Total Cost")[
  #set align(center + horizon)

  #grid(
    columns: 2,
    column-gutter: 0.5em,
    image("../src/Pareto.svg", width: 95%),
    image("../src/Total Cost.svg", width: 95%),
  )

  #v(0.3em)
  #text(size: 12pt)[
    #set par(justify: false)
    *Left:* Mode-Based captures the best schedules at any deadline. Resource-Based struggles with the full Pareto front (NSGA-II cannot evolve minimal crashing). *Right:* Adding bonus/penalty ($T_max = 250$) covers short-completion cost rises and punishes late schedules.
  ]
]

#slide(title: "Single-Objective Results")[
  #set par(justify: false)

  #text(size: 9pt)[
    #align(center)[
      #table(
        columns: (auto, 1fr, 1fr, 1fr),
        inset: 5pt,
        stroke: none,
        align: horizon,

        table.hline(stroke: 1pt),
        table.header(
          [*Metric*], [*Resource-Based*], [*Mode-Based*], [*Time-Based*],
        ),
        table.hline(stroke: 1pt),

        [*Makespan* ($s_(n+1)$)], [217.14 $plus.minus$ 0.65 d], [220.33 d], [*213.00 d*],
        table.hline(stroke: 0.6pt),

        [*Target Margin* ($T_max - s_(n+1)$)], [32.86 $plus.minus$ 0.65 d], [29.7 d], [*37.0 d*],
        table.hline(stroke: 0.6pt),

        [*Labor Cost*], [\$561,967.72 $plus.minus$ \$1,072], [*\$553,426.94*], [\$584,970.19],
        table.hline(stroke: 0.6pt),

        [*Bonus*], [\$65,711.31 $plus.minus$ \$1,298], [\$59,340.00], [*\$74,000.00*],
        table.hline(stroke: 0.6pt),

        [*Total Cost*], [\$496,256.41 $plus.minus$ \$1,094], [*\$494,086.94*], [\$510,970.19],
        table.hline(stroke: 0.6pt),

        [*Solve Time*], [1275.8 $plus.minus$ 6.9 s], [301.2 s], [*2.16 s*],
        table.hline(stroke: 1pt),
      )
    ]
  ]

  #v(0.3em)
  #my-block(title: "Key Findings")[
    *Mode-Based* achieves the best total cost. *Time-Based* provides the most extreme crashing (213 d) and is 140× faster than Mode-Based. GA is now the slowest (no NSGA-II parallelization benefit).
  ]
]

#slide(title: "Gantt Charts")[
  #set align(center + horizon)

  #grid(
    columns: 3,
    column-gutter: 0.3em,
    image("../src/Model A.svg", width: 95%),
    image("../src/Model B.svg", width: 95%),
    image("../src/Model C.svg", width: 95%),
  )

  #v(0.3em)
  #text(size: 11pt)[
    #set par(justify: false)
    *Red* = crashed activities. All three models exhibit *emergent critical-path behavior* --- selectively crashing bottleneck activities rather than uniformly. Some reordering shows the power of well-defined precedence relations.
  ]
]

#slide(title: "Sensitivity: Cobb--Douglas Elasticities")[
  #set par(justify: false)

  #grid(
    columns: (1.4fr, 1fr),
    column-gutter: 1em,
    [
      #align(center)[
        #grid(
          columns: 2,
          column-gutter: 0.2em,
          image("../src/sensitivity/oat_alpha.svg", width: 100%),
          image("../src/sensitivity/oat_beta.svg", width: 100%),
        )
        #image("../src/sensitivity/tat_alpha_beta_2panel.svg", width: 75%)
      ]
    ],
    [
      #text(size: 11pt)[
        + *Negative relationship:* Both $alpha$ (overcrowding) and $beta$ (overtime) inversely affect total cost and makespan.
        + *Lateness threshold:* Schedules are *late* (over $T_max = 250$ d) when $alpha < 0.3$ or $beta < 0.3$ --- capturing inability to accelerate under extreme inefficiency.
        + *One-factor linearity:* Despite Cobb-Douglas being non-linear per activity, aggregation across the schedule is *approximately linear* in $alpha$ and $beta$ --- justifying the time-based model's linearity assumption.
        + *Two-factor nonlinearity:* The heatmap reveals the true nonlinearity --- contour lines curve and densify at lower values.
        + *Hypothesis:* Time-based model may perform poorly when $alpha$ and $beta$ vary across activities.
      ]
    ],
  )
]

#slide(title: "Sensitivity: Bonus--Penalty Parameters")[
  #set par(justify: false)

  #grid(
    columns: (1.4fr, 1fr),
    column-gutter: 1em,
    [
      #align(center)[
        #grid(
          columns: 2,
          column-gutter: 0.2em,
          image("../src/sensitivity/oat_c_early.svg", width: 100%),
          image("../src/sensitivity/oat_c_late.svg", width: 100%),
        )
        #image("../src/sensitivity/tat_c_early_c_late_2panel.svg", width: 75%)
      ]
    ],
    [
      #text(size: 11pt)[
        + *Early bonus* ($c_"early"$): Greater bonuses *incentivize extreme crashing* --- drastically decreasing both total cost and completion time.
        + *Penalty* ($c_"late"$): More complex. Acts as a *soft constraint* for on-time completion.
        + *Critical region:* $c_"late" in (0, 1000)$ --- tradeoffs between rising labor costs and tardiness penalties are most convoluted (densely packed contours).
        + *Big-$M$ regime:* Beyond \$1000, penalties force on-time schedules that settle at lower total cost via earlier unpunished makespans.
        + Bonuses remain *gradual but clear*; penalties are *non-trivial* in the critical region.
      ]
    ],
  )
]

#slide(title: "Sensitivity: Project Deadline $T_max$")[
  #set par(justify: false)

  #grid(
    columns: (1.2fr, 1fr),
    column-gutter: 1.2em,
    [
      #align(center)[
        #image("../src/sensitivity/oat_T_max.svg", width: 100%)
      ]
    ],
    [
      #my-block(title: "Surprising Findings")[
        #text(size: 12pt)[
          + *Linear cost:* Total project cost is *almost perfectly linearly related* to the target deadline --- corroborating the time-based model's linearity assumption.
          + *Non-linear crashing:* Yet this cost is achieved through a *non-linear crashing strategy* --- the Cobb-Douglas model meets every target deadline, but the optimal makespan trajectory is non-trivial.
          + *Robustness:* The model consistently meets every deadline tested, demonstrating the *reliability* of the Cobb-Douglas approach across project horizons.
        ]
      ]
    ],
  )
]

// ========== Conclusion ==========

#section(title: "Conclusion")

#slide(title: "Conclusion")[
  #set par(justify: false)

  *Contributions:* Three novel RC-TCTP formulations using the *Cobb-Douglas production function*, relaxing the assumption of known crash costs.

  #v(0.3em)
  #text(size: 13pt)[
    + *Resource-Based* (original): non-linear MINLP, solved via NSGA-II GA. Faithful to reality but computationally heavy.
    + *Mode-Based*: discretized MILP, solved via CP-SAT. *Best optimality* --- 76.6% hypervolume, lowest total cost.
    + *Time-Based*: linear interpolation, solved via CP-SAT. *Best speed* --- 11.3s (multi) / 2.16s (single), with acceptable accuracy.
  ]

  #v(0.3em)
  *Key Insights:*
  + Sensitivity analysis confirms robustness; $alpha$/$beta$ aggregation is approximately linear, justifying the time-based simplification.
  + All models exhibit *emergent critical-path behavior* --- selectively crashing bottlenecks.
  + CP-SAT dominates GA for the discretized/linearized formulations.

  #v(0.3em)
  *Future Work:* Dynamic $alpha$/$beta$ across activities; incorporating bonus/penalty into the optimization; larger-scale benchmarks.
]

// ========== References ==========

#section(title: "References")

#references(title:"References")[
	#bibliography("../ref.bib")
]

#slide(title: "Q&A")[
  
  #set align(center + horizon)
  
  == Thank You!
  Any questions?
  
]
