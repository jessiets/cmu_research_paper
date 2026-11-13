# **From Jigsaw Puzzles to General Fragment Matching: Evaluating Strategies Under Different Constraints**

## This is the subtitle of the paper, this document both explains and embodies the submission format for authors using Word

Author

Jessie Tsai, Carnegie Mellon University Masters Program, jessiet@andrew.cmu.edu

**Abstract.** This is the abstract. The manuscript template is a single column document that allows authors to type their content into the pre-existing set of paragraph formatting styles applied to the sample placeholder text here. Throughout the document you will find further instructions on how to format your text. It is based on the ACM manuscript submission format.

**Additional Keywords and Phrases:** Insert comma delimited author-supplied keyword list, Keyword number 2, Keyword number 3, Keyword number 4

**ACKNOWLEDGEMENTS**

This section is used to thank mentors and colleagues or name the individuals or institutions that supported your research or provided special assistance, such as consultation or aid. Acknowledge any owners of copyrighted materials that have granted you permission to reproduce their work.

This section is optional. If the paper is long (\>50 pp) include it. If not, omit this page. Optionally, include a similar list of table and figures

# **Table of Contents**

[**1 Introduction	3**](#introduction)

[1.1 Context and Importance	3](#context-and-importance)

[1.2 Problem Statement and Claim	3](#problem-statement-and-claim)

[1.3 Research Objectives and Questions	3](#1.3-research-objectives-and-questions)

[1.4 Approach	4](#1.4-approach)

[**2 Background	4**](#background)

[2.1 Pairwise Matching and Jigsaw Puzzle Solving	4](#pairwise-matching-and-jigsaw-puzzle-solving)

[2.2 Matching Strategies and Available Information	5](#matching-strategies-and-available-information)

[2.3 Accuracy and Computational Efficiency	5](#accuracy-and-computational-efficiency)

[2.4 Puzzle Characteristics and Representativeness	6](#2.4-puzzle-characteristics-and-representativeness)

[**3 Related Works	6**](#related-works)

[3.1 Geometric, Visual, and Hybrid Matching	6](#3.1-geometric,-visual,-and-hybrid-matching)

[3.2 Computational Tradeoffs and Evaluation	7](#3.2-computational-tradeoffs-and-evaluation)

[3.3 Matching and Reconstruction Beyond Conventional Jigsaw Puzzles	7](#3.3-matching-and-reconstruction-beyond-conventional-jigsaw-puzzles)

[**4 Methods	8**](#4-methods)

[4.1 Research Design and Justification	8](#4.1-research-design-and-justification)

[4.2 Experimental Setting, Systems, and Data Sources	8](#4.2-experimental-setting,-systems,-and-data-sources)

[4.3 Experimental Conditions and Procedures	8](#4.3-experimental-conditions-and-procedures)

[4.4 Analysis Methods and Transferability Assessment	9](#4.4-analysis-methods-and-transferability-assessment)

[4.5 Threats to Validity	10](#4.5-threats-to-validity)

[**References	11**](#references)

[**Appendix	13**](#appendix)

1. # **Introduction** {#introduction}

   1. ## **Context and Importance** {#context-and-importance}

Matching fragmented pieces to determine which ones belong next to each other is a recurring problem in image reconstruction. In a jigsaw puzzle, a solver must identify neighboring pieces using available information, such as boundary shape, color, and texture. Related pairwise-matching problems arise in fragmented document reconstruction, torn-image reassembly, and other applications involving incomplete visual data. Although these applications differ in their fragment characteristics and reconstruction requirements, they share a fundamental challenge: determining which pairs of fragments are most likely to be adjacent.  
Different matching strategies rely on different types of evidence. Geometric strategies compare fragment boundaries, visual strategies examine image characteristics, and hybrid strategies combine multiple sources of information. Their effectiveness may depend on the available information, the visual complexity of the fragments, and the computational resources available. A strategy that achieves high matching accuracy may require more computation or memory than a simpler alternative. Consequently, selecting a matching strategy is an engineering decision involving trade-offs between effectiveness and resource consumption.  
Jigsaw puzzles provide a useful starting point for investigating these trade-offs. Their pieces can be generated under controlled conditions, and their correct adjacencies can be established as ground truth. These properties allow matching strategies to be evaluated using consistent datasets and measurements. Findings from the experiments can subsequently be compared with approaches used in other fragment-matching domains to assess whether similar strategy-selection principles may apply.

2. ## **Problem Statement and Claim** {#problem-statement-and-claim}

Existing research has explored geometric, visual, and hybrid approaches to jigsaw puzzle matching. These approaches differ in the information they use, the compatibility measures they calculate, and the computational work they require. However, selecting a suitable strategy for a particular application requires considering more than its matching accuracy. Information availability and computational requirements may also influence which strategy is appropriate under a given set of conditions.  
The problem addressed by this research is how matching strategies perform under different information and computational constraints, and how these performance differences can inform strategy selection. In particular, the study investigates whether the relative performance of geometric, visual, and hybrid strategies changes when a completed reference image is available and when puzzle characteristics vary.  
This research argues that controlled experiments on jigsaw puzzle matching can reveal how matching strategies perform under different information and computational constraints. These findings can then be compared with approaches used in other fragment-matching domains to assess whether the same strategy-selection principles may apply more broadly.  
Jigsaw puzzle matching serves as the primary experimental case study. A subsequent literature-based assessment examines similarities and differences between jigsaw matching and selected fragment-reconstruction applications. The study does not assume that results obtained from jigsaw puzzles will generalize directly to other domains; instead, it uses the comparison to identify potentially transferable principles and conditions requiring further validation.

## **1.3 Research Objectives and Questions** {#1.3-research-objectives-and-questions}

The research has two objectives. The first is to experimentally compare geometric, visual, and hybrid matching strategies under different puzzle conditions. The second is to examine how the observed performance patterns relate to approaches used in other fragment-matching domains.  
The study addresses the following research questions:

1. How do different combinations of geometric and visual features affect pairwise matching accuracy, runtime, and memory consumption under different jigsaw puzzle conditions?  
2. How does the availability of a completed reference image affect the relative performance and suitability of different matching strategies?  
3. To what extent can the observed strategy-selection principles inform pairwise-matching tasks in other fragment-reconstruction domains, and what domain-specific constraints limit their applicability?

(1) and (2) will be addressed through controlled experiments. (3) will be addressed through a literature-based comparison of jigsaw puzzle matching with selected applications, such as image and document reconstruction. This distinction defines the strength of the study’s conclusions: the experiments provide direct evidence for the tested jigsaw conditions, whereas broader applicability is assessed through similarities, differences, and limitations identified in existing research

## **1.4 Approach** {#1.4-approach}

The study will proceed in two phases.  
**Phase 1: Controlled jigsaw puzzle experiments.** Geometric, visual, and hybrid matching strategies will be evaluated using a common experimental pipeline. The experiments will distinguish between reference-free conditions, in which the matching method cannot access the completed image, and reference-image conditions, in which the completed image is available to the method. Puzzle characteristics, including visual complexity and puzzle size, will also be varied where feasible. Generated puzzles with known correct adjacencies will provide ground truth. Matching performance will be measured alongside runtime and memory consumption.  
The evaluation will focus on pairwise compatibility: estimating whether two pieces are neighbors. It will not attempt to develop or evaluate a complete puzzle-reconstruction system. A common evaluation procedure will be used to improve comparability and isolate the effects of the selected matching strategies where possible.  
**Phase 2: Literature-based transferability assessment.** Findings from the jigsaw experiments will be compared with strategies described in research on other fragment-matching applications, including image and document reconstruction. The comparison will examine the types of fragments, available information, matching features, performance requirements, and computational constraints in each domain. It will identify which aspects of the proposed strategy-selection framework appear transferable and which require domain-specific adaptations or further experiments.  
Together, these phases aim to connect a controlled evaluation of a concrete matching problem with a broader engineering question: how should a system choose among alternative matching strategies when its information and resource constraints vary?

2. # **Background** {#background}

   1. ## **Pairwise Matching and Jigsaw Puzzle Solving** {#pairwise-matching-and-jigsaw-puzzle-solving}

Pairwise matching estimates whether two pieces or fragments belong next to one another. In jigsaw puzzle solving, a matching method assigns compatibility scores to candidate pairs based on evidence that their boundaries or image content are consistent with adjacency. These scores can subsequently support decisions about neighboring pieces and the assembly of larger groups.  
Pairwise matching is distinct from complete puzzle reconstruction. A complete reconstruction system must also determine global arrangement and orientation, resolve conflicts among competing local matches, and ensure consistency across the assembled puzzle. A locally compatible pair does not necessarily belong in the correct global arrangement. This study therefore evaluates only whether two pieces are adjacent, not whether a complete puzzle can be assembled. The experiment assumes that pieces are correctly oriented; global orientation recovery and full reconstruction are outside the scope. **Figure 1** shows this boundary.  
The number of potential comparisons also grows with puzzle size. For (n) pieces, evaluating every unique unordered pair requires $\frac{n(n-1)}{2}$ candidate comparisons, so total runtime grows quadratically when all pairs are scored, scaled by the cost of each comparison. Methods that compare specific sides perform several comparisons per pair, which changes the constant factor but not the quadratic growth. Memory requirements depend on how a system represents features and stores compatibility scores. A dense representation keeps a score for every candidate and also grows quadratically, whereas a filtered or sparse representation keeps only promising candidates, which reduces storage but can discard true neighbors. Feature storage instead depends on the number of pieces and the size of each representation. For example, 499,500 pair scores stored at 64 bits each occupy about 4 MB, which may be small relative to the stored features or images. Neither computation nor score storage should be assumed to be the dominant cost in every setting; both must be considered in the context of the implementation and measured experimentally.

2. ## **Matching Strategies and Available Information** {#matching-strategies-and-available-information}

Matching strategies differ in the evidence they use to estimate whether two pieces are adjacent. This study considers three broad families: geometric, visual, and hybrid matching.  
**Geometric matching** evaluates the shapes or contours of piece boundaries. A method may represent a boundary as a sequence of coordinates or a curve and calculate how closely the boundary of one piece complements that of another. For conventional jigsaw pieces, this can involve comparing opposing boundary profiles. Geometric evidence can be informative when neighboring pieces have distinctive complementary shapes. However, pieces with similar or ambiguous boundaries may be difficult to distinguish using shape alone.  
**Color-based matching** compares image colors near candidate boundaries. For example, a method can compare corresponding pixels or color distributions along boundary strips, with lower color differences indicating greater compatibility. Its effectiveness depends on whether neighboring regions have sufficiently consistent color information. Large uniform-color regions can make color evidence less discriminative because many unrelated boundaries may have similar colors.  
**Gradient-based matching** examines changes in image intensity or color across candidate boundaries. Rather than comparing color values alone, gradient-based methods evaluate whether visual transitions continue plausibly from one piece to another. This may help distinguish boundaries that have similar overall colors but different visual transitions.  
**Texture and appearance matching** compares local patterns or broader visual characteristics near candidate boundaries. These features can help distinguish regions with similar colors but different textures or structures. Their effectiveness depends on the amount of useful visual information available, the scale of the representation, and whether the relevant patterns remain visible near fragment boundaries.  
**Hybrid matching** combines geometric and visual evidence. A hybrid method may normalize and combine separate compatibility scores or use one feature to filter candidate pairs before applying another. Combining features can improve discrimination when the information sources complement each other, but it may also increase runtime, memory consumption, and implementation complexity. The benefits depend on the specific features and combination method, rather than on hybridization alone.  
These categories describe families of approaches, not interchangeable implementations. The information available to a matching method is another important constraint. In a **reference-free** setting, the completed image is unavailable to the method, which must infer adjacency from the fragments themselves. In a **reference-image** setting, the completed image is available and can provide additional visual or spatial information, depending on how the algorithm uses it.

3. ## **Accuracy and Computational Efficiency** {#accuracy-and-computational-efficiency}

Matching quality is important, but it is not the only consideration in selecting a strategy. A method that produces more accurate pairwise matches may require more computation or memory than a simpler alternative. Conversely, a computationally inexpensive method may be suitable for a system with tight resource limits even if its matching accuracy is lower.  
This study evaluates three principal dimensions:

* **Matching accuracy**: how effectively a strategy identifies true neighboring pairs and distinguishes them from incorrect candidates. Depending on the experimental setup, precision, recall, or F1-score may supplement overall accuracy.  
* **Runtime**: the time required to compute pairwise compatibility scores under the defined experimental conditions.  
* **Memory consumption**: the memory required during matching, including any substantial storage of intermediate features or pairwise scores.

These dimensions represent different aspects of system quality. ISO/IEC 25010:2023 describes performance efficiency in terms of performance relative to the resources used under stated conditions, including time behavior, resource utilization, and capacity. This provides a useful basis for treating runtime and memory consumption as explicit evaluation criteria rather than secondary observations.  
The study will not assume that one strategy is universally superior. Instead, it will examine the conditions under which each strategy offers a useful balance of matching quality and computational cost. This approach can support conditional recommendations for systems with different requirements, such as prioritizing accuracy in one application while placing greater emphasis on runtime or memory limits in another.

## **2.4 Puzzle Characteristics and Representativeness** {#2.4-puzzle-characteristics-and-representativeness}

Puzzle size increases candidate comparisons much faster than true neighbors. A rectangular grid with $r{\ }$rows and $c$columns contain only $2n\ -\ r\ -\ c$ adjacent pairs. A 10 × 10 puzzle therefore has 4,950 candidate pairs and 180 true neighbors, whereas a 25 × 40 puzzle has 499,500 candidates and 1,935 true neighbors. A tenfold increase in pieces produces about a hundredfold increase in comparisons and reduces the share of true pairs from 3.6% to about 0.4%, which also makes overall accuracy less informative.  
Visual content affects how much evidence each feature can provide. In large uniform-color regions, many unrelated boundaries have nearly identical colors, so incorrect candidates can score as well as true neighbors and color-based matching loses discriminative value. Gradient and texture features depend on visible variation as well and may be similarly limited, whereas geometric evidence does not depend on image content. Similar fine textures can also be ambiguous: Yao and Shao (2003) report failures on natural scenes in which many pieces had similar, delicate textures.  
Generated puzzles are suited to controlled comparison because they provide exact ground truth and allow image content and puzzle size to vary systematically. They do not fully represent real puzzles, and their adequacy depends on the characteristic being tested. Image diversity and solid-color regions can be represented through source-image selection, but cutting geometry is more difficult. Square pieces provide no geometric evidence, while simulated interlocking cuts may be more exactly complementary than physical cuts and could overstate geometric matching. Digital cutting also preserves pixels up to the boundary, whereas physical puzzles may include irregular cuts, damaged pieces, glare, and scanning noise. Chung et al. (1998) note that camera and feature-extraction errors can give a similar but incorrect piece the best score, and Yao and Shao (2003) attribute reconstruction errors partly to scanner shadows that deform boundary curves. Rika et al. (2022) report that classical compatibility measures degrade sharply when a one-pixel frame is eroded from each piece, and Dirauf et al. (2025) report rapid declines for content-based solvers as simulated corruption increases. A reference image derived from the same digital source as the pieces may also be more exact than the reference available for a physical puzzle. If real puzzle data are not included, results apply only to the tested generated conditions and cannot establish how strategies would rank on physical puzzles.

3. # **Related Works** {#related-works}

## **3.1 Geometric, Visual, and Hybrid Matching** {#3.1-geometric,-visual,-and-hybrid-matching}

Early research on automated jigsaw puzzles established geometric boundary matching as a way to estimate whether two pieces fit together (Freeman & Garder, 1964\). Subsequent work explored the computational complexity of puzzle solving and its relationship to other combinatorial problems, highlighting the difficulty of finding solutions for arbitrary instances (Demaine & Demaine, 2007\). These studies provide a foundation for understanding both the geometric matching problem and the need for practical matching strategies.  
Later research expanded beyond geometry alone. Chung et al. (1998) combined boundary-shape matching with color information and compared several assembly algorithms. Their results showed that adding color could substantially improve performance over shape-only matching in their tested puzzles. Yao and Shao (2003) likewise combined shape matching with image merging, demonstrating a hybrid approach in which geometric information helps propose candidate neighbors and visual information helps evaluate them. Nielsen et al. (2008) explored image features as an alternative to shape-based matching and considered a divide-and-conquer approach to reduce the number of comparisons.  
Other work has studied pairwise compatibility more directly. Jin et al. (2014) combined edge similarity with content similarity to rank candidate pieces. Guerroui and Séridi (2020) proposed a compatibility measure that combines image features and color distance. Cho et al. (2010) examined visual compatibility measures within a probabilistic reconstruction framework. Together, these studies demonstrate that feature selection and compatibility measurement can affect matching performance, and they provide precedents for evaluating geometric, visual, and hybrid approaches.  
More recent research has also investigated the relationship between matching quality and computational efficiency. Rika et al. (2022) proposed an embedding-based compatibility approach and compared its accuracy and runtime with earlier methods. Shahar et al. (2025) studied pairwise alignment and compatibility for arbitrarily irregular image fragments, using a hybrid approach and evaluating neighborhood-level precision and recall. This work is particularly relevant to the broader motivation of the present study because it moves beyond conventional puzzle-piece geometry toward fragments with more varied shapes.

## **3.2 Computational Tradeoffs and Evaluation** {#3.2-computational-tradeoffs-and-evaluation}

The total cost of a matching system depends on both the number of comparisons and the operations performed for each comparison. Feature extraction, candidate filtering, score calculation, and result storage may contribute differently across implementations.  
Prior work has addressed aspects of this problem through approaches such as reducing comparisons, using alternative visual representations, or learning compatibility scores. Nielsen et al. (2008), for example, considered divide-and-conquer techniques to reduce comparisons, while more recent compatibility approaches have examined learned representations and computational efficiency. Such work illustrates that the efficiency of a matching system cannot be inferred from its feature family alone.  
Published results also depend on the conditions under which they are obtained. Differences in image content, puzzle size, available reference information, candidate pairs, and implementation details may influence both matching quality and runtime. Consequently, results reported by separate studies do not necessarily establish which approach would perform best if the methods were evaluated on the same instances under consistent conditions.  
Empirical software engineering provides a basis for addressing this challenge through controlled procedures, explicit measurements, and validity assessment (Wohlin et al., 2012\). The aim of the present study is not to reproduce every existing solver or to claim that prior research has neglected efficiency, but to compare selected strategies under explicitly defined conditions.

## **3.3 Matching and Reconstruction Beyond Conventional Jigsaw Puzzles** {#3.3-matching-and-reconstruction-beyond-conventional-jigsaw-puzzles}

Pairwise matching also appears in applications involving fragments that differ substantially from conventional jigsaw pieces. In document reconstruction, the useful evidence depends on how the document was destroyed. For hand-ripped documents, contours remain informative: Zhu, Zhou, and Hu (2008) found candidate matches through curve matching without application-specific features, then used a relaxation process to resolve ambiguous candidates into a globally consistent result. Richter et al. (2013) combined shape- and content-based local features, using a support vector machine to identify likely corresponding contour points on fragment pairs before evaluating alignments. This resembles the filter-then-score form of hybrid matching. For mechanically shredded documents, shape tends to be less relevant and compatibility depends largely on appearance, which is difficult for binary text with little color information (Paixão et al., 2020\). Paixão et al. (2020) learned shred embeddings so that the number of neural-network inferences scales linearly with the number of shreds, reporting comparable accuracy and a roughly 22-fold speed-up over an earlier deep-learning method on 505 strip-cut shreds, although pairwise distance computation still grows quadratically.  
Fragmented-image reconstruction presents a related but distinct problem because fragments are irregular and have no predefined sides. Kamran et al. (2018) extracted fragment boundaries and formulated inter-fragment boundary matching as a longest common subsequence problem, then used multi-piece alignment to prune incorrect matches. Le and Li (2019) used a convolutional neural network to judge whether a computed alignment between two fragments was correct, then applied loop-closure constraints during global composition. Shahar et al. (2025) used fragment geometry to reduce the candidate alignments and scored the remaining alignments using image content extrapolated beyond the fragment boundaries. These approaches illustrate that the useful evidence and reconstruction constraints depend on the properties of the fragments and the intended output.  
Despite these differences, the domains share a general structure: a system evaluates candidate relationships between fragments using available evidence, then uses those relationships to support reconstruction. Methods in each domain also trade matching quality against the cost of evaluating many candidates, and several reduce that cost through filtering or reusable representations. This common structure motivates examining whether findings about feature effectiveness, information availability, and computational costs in jigsaw matching can inform strategy selection elsewhere.  
However, the similarities should not be taken as evidence of direct transferability. Document fragments may contain linguistic structure, and findings about color or boundary shape may not apply to binary text or uniformly cut strips. Irregular image fragments may have incomplete or noncomplementary boundaries, and they require a search over possible alignments that is absent when correctly oriented pieces are compared side by side. Real-world data may also contain missing content, noise, overlap, or inconsistent image quality, and some applications may impose requirements for large-scale processing or real-time operation.

# **4 Methods** {#4-methods}

## **4.1 Research Design and Justification** {#4.1-research-design-and-justification}

	This study uses a two-phase research design consisting of a controlled computational experiment and a literature-based transferability assessment. The first phase investigates how geometric, visual, and hybrid pairwise-matching strategies perform under different information and computational constraints. The second phase compares the resulting experimental findings with approaches used in other fragment-matching domains to assess whether similar strategy-selection principles may apply more broadly. This design separates empirical conclusions supported by the jigsaw experiments from broader interpretations informed by existing literature. Following established principles of empirical software engineering, the experiment will use consistent inputs, defined performance measures, and documented execution conditions to support meaningful comparisons (Wohlin et al., 2012\).

## **4.2 Experimental Setting, Systems, and Data Sources** {#4.2-experimental-setting,-systems,-and-data-sources}

The primary experiment will use software-based jigsaw puzzle instances with known ground-truth adjacencies. Candidate matching implementations will represent geometric, visual, and hybrid strategies. A pilot study will be conducted to determine which implementations and dataset-generation tools provide compatible inputs, reproducible results, and sufficient control over puzzle characteristics.  
Where feasible, the dataset will vary puzzle size and visual complexity, including visually varied content and images containing large uniform or solid-color regions, to investigate the effects described in *Section 2.4*. The specific sizes, images, and complexity categories will be finalized after the pilot.  
The study will document the source images, generation procedures, piece geometry, and orientation assumptions. The discussion will consider the differences between generated and physical puzzles described in *Section 2.4*. If suitable real-puzzle data are available, they may be used for supplementary validation; otherwise, conclusions will be explicitly limited to the tested generated-puzzle conditions.

## **4.3 Experimental Conditions and Procedures** {#4.3-experimental-conditions-and-procedures}

The experiment will begin with pieces in their correct orientation. This scope decision isolates pairwise matching performance from the additional complexity of orientation recovery, so that differences in results can be attributed to matching evidence rather than to a method's handling of rotation. Unknown orientation would introduce another experimental variable and increase computational requirements: for four-sided pieces, the side combinations to evaluate rise fourfold, from $4n(n-1)$ to $16n(n-1){\ }$(Rika et al., 2022\). It is therefore a potential direction for future work rather than part of the current experiment.  
In the **reference-free** condition, the completed image will be withheld from the matching algorithm and used only by the evaluator to establish ground truth. In the reference-image condition, the completed image may be used by the algorithm as an additional information source, and the way each strategy uses it will be documented.  
Each selected strategy will be evaluated using the same puzzle instances and ground-truth labels where applicable. The implementations will document their feature representations, candidate-generation procedures, scoring methods, and any storage or filtering of candidate scores.  
For each run, the study will record matching performance, runtime, CPU usage, and memory consumption, together with the puzzle size and number of candidate pairs. Precision, recall, and F1-score may supplement accuracy where the distribution of positive and negative candidate pairs makes overall accuracy insufficient.  
In this study, runtime refers to elapsed wall-clock time. CPU time is the processor time consumed by the process, and CPU utilization is CPU time divided by wall-clock time. CPU utilization is a supporting measurement that helps explain runtime: a multithreaded implementation can consume more CPU time than elapsed time, whereas a method that waits on other operations consumes less. Where practical, feature extraction and pairwise scoring will be timed separately.  
The proposed overall memory measurement is peak process memory during matching. It would include feature storage, intermediate computations, compatibility scores, and runtime overhead, so a baseline would be recorded before matching begins. Where practical, stored features and compatibility scores would also be sized directly to distinguish the cost of computing pairwise scores from the cost of storing them, since these costs may scale differently with puzzle size and implementation choices. Intermediate computations would be reported separately only if the pilot shows that they can be isolated reliably.  
Specific tools depend on the implementation language, which will be selected during the pilot. If Python is used, candidate tools include time.perf\_counter for wall-clock time, time.process\_time for CPU time, operating-system peak resident set size for process memory, and tracemalloc for Python-managed allocations. Because tracemalloc may not capture memory allocated by native libraries and adds overhead, any such profiling would run separately from timing runs. To keep measurements consistent, all strategies and repeated runs will use the same hardware, operating environment, instrumentation, and measurement boundaries, with thread settings and dependency versions recorded. The pilot will confirm whether these measurements are feasible, finalize the tools and measurement boundaries, and determine the number of repetitions.

## **4.4 Analysis Methods and Transferability Assessment** {#4.4-analysis-methods-and-transferability-assessment}

The experimental results will be summarized by matching strategy and puzzle condition using appropriate measures of central tendency and variability. Paired comparisons will be used where strategies are evaluated on the same puzzle instances and the data support such comparisons. Statistical tests will be selected after examining the collected data and relevant assumptions. Effect sizes and confidence intervals will be reported where feasible.  
The analysis will identify how feature combinations and reference-image availability relate to matching performance and computational cost. It will examine whether observed trade-offs are consistent across the tested image characteristics and puzzle sizes, without assuming in advance that one strategy will be universally superior.  
In the second phase, a structured literature-based comparison will examine matching approaches in selected fragment-reconstruction domains, such as shredded-document and torn-image reconstruction. For each domain, the review will record the fragment characteristics, features used, availability of reference information, evaluation measures, and computational constraints described in the literature. These characteristics will be compared with the conditions and trade-offs observed in the jigsaw experiments.  
The purpose of this comparison is to assess whether similar strategy-selection principles appear relevant across domains, identify domain-specific differences that may limit their applicability, and determine which conclusions require further empirical validation. The second phase will not be treated as experimental proof of generalization. Any strategy-selection framework produced by the study will therefore be presented as guidance grounded in the tested conditions and the supporting literature, with its limitations stated explicitly.

## **4.5 Threats to Validity** {#4.5-threats-to-validity}

Potential threats include limited representativeness of generated puzzles, dependence on source-image characteristics, differences between matching implementations, and sensitivity of runtime and memory measurements to the execution environment. The transferability assessment also depends on the coverage and quality of the selected literature. These limitations will be documented, and conclusions will be restricted to the conditions evaluated. Further experiments using physical puzzles and non-jigsaw fragments will be identified where necessary.

# **5 Results**

(Currently still going through experiments. Will add to the Results section in the following days.)

# **6 Discussion**

## **6.1 Interpretation of Results**

## **6.2 Rebuttals**

## **6.3 Qualifiers and Threats to Validity**

## **6.4 Impacts**

# **References** {#references}

Cho, T. S., Avidan, S., & Freeman, W. T. (2010). A probabilistic image jigsaw puzzle solver. In *Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition* (pp. 183–190). [https\://doi.org/10.1109/CVPR.2010.5540212](https://doi.org/10.1109/CVPR.2010.5540212)

Chung, M. G., Fleck, M. M., & Forsyth, D. A. (1998). Jigsaw puzzle solver using shape and color. In *Proceedings of the Fourth International Conference on Signal Processing* (Vol. 2, pp. 877–880). [https\://doi.org/10.1109/ICOSP.1998.770751](https://doi.org/10.1109/ICOSP.1998.770751)

Demaine, E. D., & Demaine, M. L. (2007). Jigsaw puzzles, edge matching, and polyomino packing: Connections and complexity. *Graphs and Combinatorics, 23*(Suppl. 1), 195–208. [https\://doi.org/10.1007/s00373-007-0713-4](https://doi.org/10.1007/s00373-007-0713-4)

Dirauf, R., Wolz, F., Zanca, D., & Eskofier, B. (2025). *Benchmarking content-based puzzle solvers on corrupted jigsaw puzzles* (arXiv:2507.07828). arXiv. Accepted at ICIAP 2025\. 

Freeman, H., & Garder, L. (1964). Apictorial jigsaw puzzles: The computer solution of a problem in pattern recognition. *IEEE Transactions on Electronic Computers, EC-13*(2), 118–127. [https\://doi.org/10.1109/PGEC.1964.263781](https://doi.org/10.1109/PGEC.1964.263781)

Gallagher, A. C. (2012). Jigsaw puzzles with pieces of unknown orientation. In *Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition* (pp. 382–389). [https\://doi.org/10.1109/CVPR.2012.6247699](https://doi.org/10.1109/CVPR.2012.6247699)

Guerroui, N., & Séridi, H. (2020). Solving computational square jigsaw puzzles with a novel pairwise compatibility measure. *Journal of King Saud University \- Computer and Information Sciences, 32*(8), 928–939. 

ISO/IEC. (2023). *Systems and software engineering — Systems and software Quality Requirements and Evaluation (SQuaRE) — Product quality model* (ISO/IEC 25010:2023). International Organization for Standardization.

Jin, S.-Y., Lee, S., Azis, N. A., & Choi, H.-J. (2014). Jigsaw puzzle image retrieval via pairwise compatibility measurement. In *Proceedings of the 2014 International Conference on Big Data and Smart Computing* (pp. 123–127). [https\://doi.org/10.1109/BIGCOMP.2014.6741421](https://doi.org/10.1109/BIGCOMP.2014.6741421)

Kamran, H., Zhang, K., Li, M., & Li, X. (2018). An LCS-based 2D fragmented image reassembly algorithm. In *Proceedings of the 13th International Conference on Computer Science and Education* (pp. 687–692). [https\://doi.org/10.1109/ICCSE.2018.8468808](https://doi.org/10.1109/ICCSE.2018.8468808) 

Le, C., & Li, X. (2019). JigsawNet: Shredded image reassembly using convolutional neural network and loop-based composition. *IEEE Transactions on Image Processing, 28*(8), 4000–4015. [https\://doi.org/10.1109/TIP.2019.2903298](https://doi.org/10.1109/TIP.2019.2903298)

Nielsen, T. R., Drewsen, P., & Hansen, K. (2008). Solving jigsaw puzzles using image features. *Pattern Recognition Letters, 29*(14), 1924–1933. [https\://doi.org/10.1016/j.patrec.2008.05.027](https://doi.org/10.1016/j.patrec.2008.05.027)

Paixão, T. M., Berriel, R. F., Boeres, M. C. S., Koerich, A. L., Badue, C., De Souza, A. F., & Oliveira-Santos, T. (2020). Fast(er) reconstruction of shredded text documents via self-supervised deep asymmetric metric learning. In *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition* (pp. 14343–14351).

Richter, F., Ries, C. X., Cebron, N., & Lienhart, R. (2013). Learning to reassemble shredded documents. *IEEE Transactions on Multimedia, 15*(3), 582–593. [https\://doi.org/10.1109/TMM.2012.2235415](https://doi.org/10.1109/TMM.2012.2235415)

Rika, D., Sholomon, D., David, E., & Netanyahu, N. S. (2022). *Edge2Vec: A high quality embedding for the jigsaw puzzle problem* (arXiv:2211.07771). arXiv.

Shahar, O. I., Elkin, G., & Ben-Shahar, O. (2025). *Pairwise alignment & compatibility for arbitrarily irregular image fragments* (arXiv:2507.09767). arXiv. [https\://doi.org/10.1007/978-3-032-31438-3\_11](https://doi.org/10.1007/978-3-032-31438-3_11)

Wohlin, C., Runeson, P., Höst, M., Ohlsson, M. C., Regnell, B., & Wesslén, A. (2012). *Experimentation in software engineering*. Springer. [https\://doi.org/10.1007/978-3-642-29044-2](https://doi.org/10.1007/978-3-642-29044-2)

Yao, F.-H., & Shao, G.-F. (2003). A shape and image merging technique to solve jigsaw puzzles. *Pattern Recognition Letters, 24*(12), 1819–1835. [https\://doi.org/10.1016/S0167-8655(03)00006-0](https://doi.org/10.1016/S0167-8655\(03\)00006-0)

Zhu, L., Zhou, Z., & Hu, D. (2008). Globally consistent reconstruction of ripped-up documents. *IEEE Transactions on Pattern Analysis and Machine Intelligence, 30*(1), 1–13. [https\://doi.org/10.1109/TPAMI.2007.1163](https://doi.org/10.1109/TPAMI.2007.1163)

# **Appendix** {#appendix}

|  | Input pieces             Piece A and Piece B, correctly oriented       \|       v Feature extraction   Geometric: opposing boundary profiles                                 Visual: boundary colors, gradients, or local patterns       \|       v Pairwise scoring     Compare the facing sides of A and B                                 Hybrid: combine scores, or filter with one feature first       \|       v Output                     Ranked or thresholded candidate pairs \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- \- Out of scope           Global arrangement, orientation recovery, conflict resolution  |
| :---- | :---- |

**Figure 1\.** Generic pairwise-matching pipeline. The figure illustrates the strategy families; the exact features, scoring functions, and decision rule will be specified after the pilot.