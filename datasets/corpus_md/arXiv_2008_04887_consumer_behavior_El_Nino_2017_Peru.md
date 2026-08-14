|     |     | Impact   | of natural | disasters  |     | on  | consumer |     | behavior: | case | of  |
| --- | --- | -------- | ---------- | ---------- | --- | --- | -------- | --- | --------- | ---- | --- |
|     |     | the 2017 | El Nin˜o   | phenomenon |     |     | in Peru  |     |           |      |     |
Hugo Alatrista-Salas1 ID , Vincent Gauthier 2* ID , Miguel Nunez-del-Prado1* ID ,
Becker2
|     |     | Monique       | ID             |     |              |       |       |      |     |     |     |
| --- | --- | ------------- | -------------- | --- | ------------ | ----- | ----- | ---- | --- | --- | --- |
|     |     | 1 Universidad | del Pac´ıfico, |     | Av Salaverry | 2020, | Lima, | Peru |     |     |     |
2 Laboratory SAMOVAR, Telecom SudParis, Institut Polytechnique de Paris, France
0202 guA 11  ]IS.sc[  1v78840.8002:viXra * corresponding authors: vincent.gauthier@telecom-sudparis.eu,
m.nunezdelpradoc@up.edu.pe
Abstract
El Nin˜o is an extreme weather event featuring unusual warming of surface waters in the
eastern equatorial Pacific Ocean. This phenomenon is characterized by heavy rains and
|     |     | floods that | negatively | affect | the economic |     | activities | of the | impacted | areas. |     |
| --- | --- | ----------- | ---------- | ------ | ------------ | --- | ---------- | ------ | -------- | ------ | --- |
Understanding how this phenomenon influences consumption behavior at different
granularity levels is essential for recommending strategies to normalize the situation.
With this aim, we performed a multi-scale analysis of data associated with bank
transactions involving credit and debit cards. Our findings can be summarized into two
main results: Coarse-grained analysis reveals the presence of the El Nin˜o phenomenon
and the recovery time in a given territory, while fine-grained analysis demonstrates a
change in individuals’ purchasing patterns and in merchant relevance as a consequence
of the climatic event. The results also indicate that society successfully withstood the
natural disaster owing to the economic structure built over time. In this study, we
present a new method that may be useful for better characterizing future extreme
events.
Introduction
El Nin˜o–Southern Oscillation (ENSO) is a climatic phenomenon consisting of a
temperature increase in the equatorial Pacific area. ENSO has a 2-7 years fluctuation
period, with a warm phase known as El Nin˜o and a cold phase known as La Nin˜a. A
|     |     | crucial | indicator of the | presence | of  | El Nin˜o | is the | variation | of the | sea surface |     |
| --- | --- | ------- | ---------------- | -------- | --- | -------- | ------ | --------- | ------ | ----------- | --- |
temperature, which causes changes in the worldwide climate. At the end of 2016 and in
early 2017, ENSO had an abrupt change that caused heavy rains and floods. This
atypical phenomenon is called El Nin˜o costero. According to United Nations Office for
the Coordination of Humanitarian Affairs (OCHA) [1], the first three months of 2017
witnessed the highest amount of human and material loss in Lima and in the northern
regions of Peru caused by the coastal ENSO phenomenon. In this paper, we focus on
|     |     | two main    | events that | occurred | in February |              | and March |        | 2017 (see,     | Fig. 1).   |     |
| --- | --- | ----------- | ----------- | -------- | ----------- | ------------ | --------- | ------ | -------------- | ---------- | --- |
|     |     | In February | 2017,       | strong   | rainfall    | accumulation |           | led to | 39 fatalities, | 14 injured |     |
individuals, 8,299 affected individuals, 19 destroyed bridges, 29 affected bridges,
11.92 km of damaged roads, 140.39 km of affected roads, 191.5 ha of destroyed crops,
1,472 ha of affected crops. In addition, the northwest region of Peru and the southern
Arequipa region were both in a state of emergency. The second event in March 2017
inflicted more damages on the country, leading to 98 deaths, over 1 million affected
| August | 12, 2020 |     |     |     |     |     |     |     |     |     | 1/28 |
| ------ | -------- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---- |

individuals, 639 affected bridges, 1,722 affected schools, 351 injured individuals, 20
missing individuals, 605 affected hospitals, 8,481 km of affected roads, 230,317 damaged
houses, and 5,244 ha of deteriorated crops, as illustrated in Fig. 2.
In this work, the goal is not to estimate the macroeconomic impact of extreme
climatic events such as in [2,3], but to better understand how resilience leads a
population to organize itself after a shock through the prism of the population
purchasing behavior. In recent years, in Peru, the El Nin˜o phenomenon has harmed the
economy of Peru due to the damage it caused to the country’s infrastructures. However,
it has also directly impacted the economic life of Peruvian citizens. For instance, the
last event of El Nin˜o costero in 2017, led to rising food prices of lemon and garlic, which
are two basic foodstuff in the Peruvian diet. The availability of food supplies was
generally due to the degradation of the road network. The degradation of the
infrastructure also made it difficult to supply, water, vegetables, and meat to major
cities. The unavailability of food items triggered panic buying of the missing items
throughout retail stores in impacted and non-impacted areas. It remains unclear how
these reported events impacted the consumption behavior of people. In addition, the
dynamics of individual purchases during a time of crisis remain poorly studied, which
gives us further motivations to study purchase behavior from a time perspective during
the transient period of the El Nin˜o event of 2017.
Fig 1. Peru severe weather and floods map taken from [4]. Reprinted with permission
from the EU Emergency Response Coordination Centre (ERCC).
In this study, we aimed to determine the resilience of retail structures by measuring
the collective response of consumers living in Lima’s greater area. In particular, we
developed our analysis to better understand the consumer habit changes during a
period of climatic stress. To achieve this goal, we performed a multi-scale analysis of the
consumption patterns based on a credit and debit card transaction dataset of roughly 6
million Peruvian citizens gathered over a 2-year period from 2016 to 2017. In this study,
we focused exclusively on the city of Lima for two reasons. First, it is both the political
and economic capital of Peru, containing roughly 1/3 of the country’s population.
Second, despite the fact that the data are available for the entire country, data from the
August 12, 2020 2/28

Fig 2. Peru severe weather map taken from [4]. Reprinted with permission from the
|     |     | EU Emergency | Response | Coordination |     | Centre | (ERCC). |     |     |
| --- | --- | ------------ | -------- | ------------ | --- | ------ | ------- | --- | --- |
other regions are sparse due to the lack of bank coverage in certain areas of the country,
|     |     | which makes | it difficult | to  | have even | coverage | of the country. |     |     |
| --- | --- | ----------- | ------------ | --- | --------- | -------- | --------------- | --- | --- |
We first focus on techniques to measure the dynamics of consumer behavior at the
macroscopic level to evaluate our central hypothesis that consumer behavior shifted in
the aftermath of the 2017 ENSO events. This phenomenon impacted the city of Lima
twice: once in mid-February and once at the end of March. We demonstrate that other
|     |     | shocks did | not impact | consumer | behavior |     | as much as these | two events. |     |
| --- | --- | ---------- | ---------- | -------- | -------- | --- | ---------------- | ----------- | --- |
At the regional level, we examined people’s consumption patterns through individual
|     |     | mobility | models. | We observed | that | purchase | behavior patterns | changed | as a |
| --- | --- | -------- | ------- | ----------- | ---- | -------- | ----------------- | ------- | ---- |
consequence of the ENSO, but in a non-homogeneous way. We also examined how
specific merchants responded during the events. Our main finding was that despite the
fact that the overall economic activity slowed in response to the events, businesses
responded differently during the events and in their aftermath. In this paper, we aim to
improve preventative measures that can mitigate climatic events and improve the
effectiveness of recovery efforts. Our contributions are summarized as follows:
1. We captured anomalous events using the Kullback-Leibler divergence (KLD). The
main purpose was to recognize a significant change in the purchase distribution of
|     |     | the | population | over time | as an | indicator | of an anomalous | event. |     |
| --- | --- | --- | ---------- | --------- | ----- | --------- | --------------- | ------ | --- |
2. We measured the changes in people’s behavior using the mobility Markov chain
(MMC) model. The basic principle was to quantify changes in both individual
|     |     | purchase | categories | and | frequent | locations. |     |     |     |
| --- | --- | -------- | ---------- | --- | -------- | ---------- | --- | --- | --- |
3. We quantified how individual merchants reacted during an event by studying the
evolution of the PageRank of each merchant in the transaction graph. Here, using
the PageRank enables us to characterize how the attractiveness of a merchant
|        |          | compares | to  | others. |     |     |     |     |      |
| ------ | -------- | -------- | --- | ------- | --- | --- | --- | --- | ---- |
| August | 12, 2020 |          |     |         |     |     |     |     | 3/28 |

4. We measured the evolution of the core/periphery structure of the transaction
graph during the events.
In facing extreme climatic events, resilience has emerged as a key concept for
understanding how communities and systems are able to absorb and adapt to stress and
shocks [5,6]. Recently the National Academies of Sciences, Engineering, and Medicine
released a study [7] on strengthening supply chain resilience in the aftermath of a
hurricanes. Four keys domains were identified that must be maintained in order to foster
the resilience of society: power and communications networks, food and water supplies,
fuel supplies, and medical and pharmaceutic supplies. Resilience is generally studied
with respect to the ecosystem, and few works [8–12] have explored and analyzed the
resilience of social systems facing extreme climatic events. Wang et al. [8] and Guan et
al. [10] studied Hurricane Sandy through the lens of human mobility perturbation.
Bagrow et al. [13] explored the societal response to external disturbances, such as
bomb attacks and earthquakes, by studying mobile phone communication patterns.
Niles et al. [11] and Eyre et al. [14] studied social media usage during a climatic event.
In particular, they found differences in tweet volume for keywords depending on the
disaster type, with people using Twitter more frequently in preparation for hurricanes
and for real-time recovery information on tornado and flooding events. With the same
goal, in [12], the authors analyzed emotion-exchange patterns that arise from Twitter
messages sent during emergency events. Additionally, in a joint work by Banco Bilbao
Vizcaya Argentaria (BBVA Data & Analytics: https://www.bbvadata.com/) and UN
Global Pulse (UN Global Pulse: https://www.unglobalpulse.org/), Martinez et
al. [9] analyzed bank debit and credit card payments and ATM cash withdrawals to map
and quantify how individuals were impacted by and recovered from hurricane Odile.
The following works [15–18] analyzed customer behavior by studying the sequence of
purchases through credit and debit cards. For instance, in [15], the authors used the
Sequitur algorithm [19] to classify user spending behavior and characterize people’s
lifestyles according to their temporal purchase sequences. In addition, Leo et al. [16,17]
used a detection algorithm to characterize people purchase sequences characterized by
the merchant category code (MCC) [20]. Finally, another model based on retail
customer data [18] identified temporal regularities in buying behavior. The authors
grouped weekly customer buying patterns using a k-means clustering algorithm to
extract groups of behaviors G per user.
u
Instead of using debit and credit card data to characterize user spending behavior,
in [21,22], the authors attempted to characterize cities based on the economic activity
of their residents. Youn et al. [21] created a model to predict how individual business
types systematically change as the city size increases, shedding light on the processes of
innovation and economic differentiation. To build the model, the authors used the
National Establishment Time Series dataset. The authors used approximately 50
million shopping transactions of 91,000 customers between January 1, 2007 and June 1,
2015 in Leghorn province, Italy. In [22], the authors demonstrated that urban
socioeconomic quantities and individual spending activity scaled superlinearly with city
size. The approach was assessed through bank card transactions of both debit and
credit cards of Spanish clients of Banco Bilbao Vizcaya Argentaria (BBVA) with a
dataset containing 178 million transactions made by 4.5 million clients in 2011.
To the best of our knowledge, no research thus far has been conducted to capture
the fine-grained impact of extreme climatic events on the spending behavior of
individuals and small businesses. In this study, we aim to provide a deeper
understanding of retail distribution in the aftermath of a natural disaster.
August 12, 2020 4/28

Results
|     |     | Kullback-Leibler |              | divergence | (KLD)              | analysis  | of   | the bank |     |
| --- | --- | ---------------- | ------------ | ---------- | ------------------ | --------- | ---- | -------- | --- |
|     |     | transaction      | distribution |            |                    |           |      |          |     |
|     |     | To investigate   | how          | the ENSO   | events in February | and March | 2017 | impacted |     |
consumption patterns in Lima, we examined how the relative frequency of merchant
categories evolved in time using the KLD. In addition, we demonstrate in Fig. 3(a) that
customers’ indeed slowed significantly both in number and volume during the first event
of February 2017. Furthermore, a smaller number of transactions was observed during
the second event in March, but the magnitude was less than that of the February event.
|     |     | The same | behavior | was observed | for cash withdrawal | (see | Fig. 3(b)). |     |     |
| --- | --- | -------- | -------- | ------------ | ------------------- | ---- | ----------- | --- | --- |
As a reference, Fig. 3c illustrates the distribution of the share of spending in each
category of purchases (VISA Merchant Category Classification MCC) in our dataset.
The figure displays only the 50 most consumed categories throughout the country
averaged throughout our dataset. It can be observed that the distribution of the
frequency of each category of purchases follows a Zipf-like distribution with dominant
purchases in for food-related stores (i.e., grocery stores and supermarkets), as expected.
|     |     | A   |                      |                    | B   |      |     |     |     |
| --- | --- | --- | -------------------- | ------------------ | --- | ---- | --- | --- | --- |
|     |     |     | v e te r in a r      | y s e r v i c e s  |     | 10−1 |     |     |     |
|     |     | C   | taxica b s a n d l   | i m o u s i n e s  |     |      |     | D   |     |
|     |     |     | s p e c i a lt y r e | t ai l s t o r e s |     | 10−2 |     |     |     |
miscellaneoushomefurnishing electri c , g a s , w a t e r u t i li t ie s
|     |     |     | elementaryandsecondaryschools |     |     | 10−3 |     |     |     |
| --- | --- | --- | ----------------------------- | --- | --- | ---- | --- | --- | --- |
wholesaleclubs
hardwarestores
|     |     |     | dentistsandorthodontists |     |     | 10−4 |     |     |     |
| --- | --- | --- | ------------------------ | --- | --- | ---- | --- | --- | --- |
men’sandboy’sclothing
|     |     |     | theatricalproducers | jewelry |     | 10−5 |     |     |     |
| --- | --- | --- | ------------------- | ------- | --- | ---- | --- | --- | --- |
conveniencestores
membershipclubs
|     |     |     | bookstores |     |     | 10−6 |     |     |     |
| --- | --- | --- | ---------- | --- | --- | ---- | --- | --- | --- |
computers
|     |     |     |     | b l u a s nc li h n i e le s |     | 10−7 |     |     |     |
| --- | --- | --- | --- | ---------------------------- | --- | ---- | --- | --- | --- |
travelagencies
o p t ic ia n s
|     |     |     |                                                     | fu r n it u re |     | 10−8 |         |         |     |
| --- | --- | --- | --------------------------------------------------- | -------------- | --- | ---- | ------- | ------- | --- |
|     |     |     | healthandbeautyshops                                |                |     | 100  | 200 300 | 400 500 |     |
|     |     |     | men’sandwomen’sclothingstores motionpicturetheaters |                |     |      | rank    |         |     |
carandtruckdealers
automotiveserviceshops
telecommunicationsequipment
drinkingplaces
women’sready-to-wearstores barberandbeautyshops
sportsapparelstores
automotiveparts
faxservices
buildingmaterialsstores
shoestores
insurancesales lodging
familyclothingstores
electronicsales
fastfoodrestaurants
financialinstitutions
taxpayments hospitals
drugstoresandpharmacies
universities,andprofessionalschools
betting
servicestations
eatingplacesandrestaurants departmentstores
grocerystores,supermarkets
|     |     |     |     |     | 10−2 |     |     | 10−1 |     |
| --- | --- | --- | --- | --- | ---- | --- | --- | ---- | --- |
sk(share)
Fig 3. Bank transaction time series and distribution. a) Transaction volume (red) and
frequency (blue) in time. b) Transaction frequency S by type, where the transaction
k
type is defined by the merchant category code (MCC) of a merchant (only the 50 most
frequent MCC codes are displayed). c) Full distribution of the MCC distribution.
| August | 12, 2020 |     |     |     |     |     |     |     | 5/28 |
| ------ | -------- | --- | --- | --- | --- | --- | --- | --- | ---- |

To further explore the evolution of the consumption pattern in response to the
events, weusedtwodifferentdivergencemeasure (1) and (2) toquantifythedeviation
|     |     |     |     |     |     |     |     | D D |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
of the purchase behavior at a given time from normal purchase behavior. To compute
the purchase distribution we classified each purchase record with its MCC information
into 15 different categories based on the Classification of Individual Consumption
According to Purpose (CIOCOP), as displayed in Table 3. With the divergence measure
(1) (see Fig. 4(a)) defined in (2), we measured the divergence of the distribution of the
D
S(t)
purchase behavior (made in district i of the greater Lima area during the interval
i
[t,t+w]) from the average consumption behavior of the entire country in each purchase
|     |     |     | S¯. |     |     | (2) |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
category With the divergence (see Fig. 4(b)) defined in (3) we used a slightly
D
different approach by computing the average KLD between S(t) , the purchase behavior
i
|     |     | in district | i          | at time t    | and the | purchase | behavior  | at a reference | date.        |     |     |
| --- | --- | ----------- | ---------- | ------------ | ------- | -------- | --------- | -------------- | ------------ | --- | --- |
|     |     |             | The metric | (1) displays | a       | smoothed | evolution | of the KLD     | highlighting | the |     |
|     |     |             |            | D            |         | (2)      |           |                |              |     |     |
macroevolution, while metric displays a more detailed the evolution of the KLD,
D
including characteristic weekly behavior with relatively stable behavior weekdays and
|     |     | different | behavior | during | weekends. |     |     |     |     |     |     |
| --- | --- | --------- | -------- | ------ | --------- | --- | --- | --- | --- | --- | --- |
In Fig. 4(a) and 4(b), we present the average divergence of all districts of Lima. We
can observe that with both divergence measures (1) and (2) the ENSO events in
|     |     |     |     |     |     |     |     | D D |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
mid-February and mid-March appear very distinctly. This suggests that purchases made
in certain categories temporary shifted toward other categories in response to the ENSO
events. In Fig. S2 in the Supporting Information section, we present the evolution of the
KLD at the district level and observe that not all districts responded evenly to the
events.
|     |     |     | a   |     |     |     | b   |          |            |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | -------- | ---------- | --- | --- |
|     |     |     |     |     |     |     | 4   | Feb ENSO | March ENSO |     |     |
|     |     |     | 0.8 |     |     |     |     | event    | event      |     |     |
75-quantiles
|     |     |     | Feb ENSO | March ENSO  | Easter | Mother’s day |     |     |     | 50-quantiles |     |
| --- | --- | --- | -------- | ----------- | ------ | ------------ | --- | --- | --- | ------------ | --- |
|     |     |     |          | event event |        |              |     |     |     | 25-quantiles |     |
|     |     |     | 0.6      |             |        |              | 3   |     |     |              |     |
Mother’s day
|     |     |     | )1(   |     |     |     | )2( 2 |     |     |     |     |
| --- | --- | --- | ----- | --- | --- | --- | ----- | --- | --- | --- | --- |
|     |     |     | D 0.4 |     |     |     | D     |     |     |     |     |
1
0.2
|     |     |     | 0.0Jan | Fev Mar | Apr  | May | Jun 0Jan | Fev Mar | Apr  | May | Jun |
| --- | --- | --- | ------ | ------- | ---- | --- | -------- | ------- | ---- | --- | --- |
|     |     |     |        |         | 2017 |     |          |         | 2017 |     |     |
|     |     |     |        | (1)     |      | (2) |          |         |      |     |     |
Fig 4. Divergence and of various districts of Lima. The average divergence
|     |     |     |     | D   | D   |     |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
over all districts of Lima as well as the 25th, 50th, and 75th quantile are plotted in
|     |     |           |        |            | a)  |            | (1). | b)         | (2). |     |     |
| --- | --- | --------- | ------ | ---------- | --- | ---------- | ---- | ---------- | ---- | --- | --- |
|     |     | different | shades | of orange. |     | Divergence |      | Divergence |      |     |     |
|     |     |           |        |            |     |            | D    |            | D    |     |     |
Causality Analysis of the ENSO Over the Individual Purchasing
Behaviors
To determine whether all the district of Lima were affected by the event uniformly, we
performed a causal impact analysis [23] on the purchase patterns in each district of
Lima after the first event in February. We discovered three modes: districts were
negatively impacted, districts that continued to function as usual, and districts that
experienced an increase in purchases. Fig. 5 presents the causal impact analysis for 42
districts of Lima, using the Callao series as s control. As a result, three different effects
of El Nin˜o can be observed. Fig. 5(a) is an example of a decreasing trend in the
post-intervention time, displaying a negative impact after the appearance of El Nin˜o.
These districts include Lima, Cieneguilla, San Martin de Porres, Ate, San Juan de
Lurigancho, Pucusana, Lurigancho, Los Olivos, Ancon, Chorrillos, Santa Rosa, San
Bartolo, Jesus Maria, Surquillo, Santa Maria del Mar, Villa el Salvador, Punta
| August | 12, 2020 |     |     |     |     |     |     |     |     |     | 6/28 |
| ------ | -------- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---- |

Hermosa, Lince, Lurin, and La Victoria. In contrast, the increasing trend in Fig. 5(b)
reveals a positive impact of El Nin˜o in Pachacamac, Carabayllo, San Isidro, San Borja,
Santa Anita, El Agustino, Rimac, Santiago de Surco, Pueblo Libre, Bren˜a, Punta
and
Negra districts. In addition, Fig. 5(c) displays a neutral effect in the post-intervention,
which signifies that El Nin˜o did not significantly affect the remaining districts. To
summarize the results Fig. 5(d) illustrates the results of the decreasing, increasing, and
stable trends in green, yellow and red, respectively. We note that the affected districts
|     |     | are close | to the Huaycoloro, | Chill´on, | Lur´ın, and R´ımac | rivers causing | floods. |     |
| --- | --- | --------- | ------------------ | --------- | ------------------ | -------------- | ------- | --- |
|     |     |           | a                  |           | d                  |                |         |     |
0
−20
|     |     |     | Lima Cieneguilla        | LosOlivos Ancon      | SantaMariadelMar VillaelSalvador |     |     |     |
| --- | --- | --- | ----------------------- | -------------------- | -------------------------------- | --- | --- | --- |
|     |     |     | SanMartindePorres       | Chorrillos           | PuntaHermosa                     |     |     |     |
|     |     |     | Ate SanJuandeLurigancho | SantaRosa SanBartolo | Lince Lurin                      |     |     |     |
|     |     |     | Pucusana                | JesusMaria           | Lavictoria                       |     |     |     |
|     |     |     | Lurigancho              | Surquillo            |                                  |     |     |     |
|     |     |     | b 10.0                  |                      |                                  |     |     |     |
7.5
5.0
2.5
0.0
−2.5
|     |     |     | Pachacamac           | SantaAnita       | PuebloLibre      |     |     |     |
| --- | --- | --- | -------------------- | ---------------- | ---------------- | --- | --- | --- |
|     |     |     | Carabayllo SanIsidro | ElAgustino Rimac | Brena PuntaNegra |     |     |     |
|     |     |     | c SanBorja           | SantiagodeSurco  |                  |     |     |     |
2
0
−2
|     |     |     | 01/02/2017 01/03/2017 | 01/04/2017 01/05/2017 | 01/06/2017        |     |     |     |
| --- | --- | --- | --------------------- | --------------------- | ----------------- | --- | --- | --- |
|     |     |     | Comas PuentePiedra    | SanMiguel VillaMaria  | LaMolina Barranco |     |     |     |
|     |     |     | SanLuis               | Independencia         | Chaclacayo        |     |     |     |
|     |     |     | Magdalenadelmar       | SanJuanMirafor        | Mirafores         |     |     |     |
Fig 5. Causal impact at the districts level for February 2017. a) List of districts that
were negatively impacted. b) List of districts that were positively impacted. c) List of
districts that experienced a neutral impact. d) Map of Lima showing the districts with
|     |     | a negative | (red), positive | (green)  | and neutral (yellow) | impact. |     |     |
| --- | --- | ---------- | --------------- | -------- | -------------------- | ------- | --- | --- |
|     |     | Individual | purchasing      | behavior |                      |         |     |     |
In this subsection, we focus on the impact of the El Nin˜o phenomenon on people
through individual MMC as a proxy for whether an individual was affected. The official
Peruvian definition refers to a person, animal, territory, or infrastructure suffering
disturbance in its environment due to the effects of a phenomenon. Immediate support
may be required to reduce the effects of the disorder to continuing regular activity [24].
Under normal conditions, people tend to buy items from the same categories, such as
”Food and non-alcoholic beverages”, ”Clothing and footwear”, and ”Transportation”.
However, in the presence of a disruptive phenomenon, frequent purchase categories can
change. Thus, the stationary vector of the MMC model represents the probability of
buying from a given merchant and therefore from the category. It should be noted that
merchants belonging to the same purchase category are merged, and their respective
probabilities are added. Finally, the categories are sorted according to their weights.
With respect to the variation in purchase categories for an individual i over time, we
used four weeks of individual historical consumption data to compute the stationary
|     |     | vector π | . Thus, we | built a set of | consumption stationary | vectors |     |     |
| --- | --- | -------- | ---------- | -------------- | ---------------------- | ------- | --- | --- |
t
csv = π ,π ,...,π shifted by one week for individual i. Accordingly, we used
|     |     | i { | t t+1 | t+n } |     |     |     |     |
| --- | --- | --- | ----- | ----- | --- | --- | --- | --- |
the normalized discounted cumulative gain metric (see Fig. 7) to measure the variability
| August | 12, 2020 |     |     |     |     |     |     | 7/28 |
| ------ | -------- | --- | --- | --- | --- | --- | --- | ---- |

between two consecutive consumption patterns π and π belonging to individual i.
t t+1
Finally, we averaged the variations for all individuals living in different districts of Lima.
Fig. 6 reveals a change in purchase patterns in all districts on approximately
February 15. First, the buying categories changed noticeably in residential areas
compared to vacation property districts, such as Cieneguilla, Santa Rosa, San Bartolo,
and Pucusana. Second, in residential districts, people could either not reach gas
stations, or gas stations suffered a fuel shortage due to infrastructure degradation.
Therefore, individuals tended to use more public transportation services, such as Uber,
and Cabify. There was also an increase in purchases in the insurance, home furniture,
and health categories. Finally, vacation property districts demonstrated an increase in
the health and technology categories, while the clothing category decreased.
Sanisidro Losolivos Lima Sanluis Ancon Cieneguilla
1.10.00
0.75
0.50
0.25
0.00
Sanborja Santaanita Sanmartindeporres Magdalenadelmar Sanmiguel Elagustino
1.00
0.75
0.05.08
0.25
0.00
Villamariadeltriu Comas Independencia Chorrillos Sanjuandemiraflores Santarosa
1.00
0.75
0.50
0.25
0.00.06
Sanbartolo Lamolina Rimac Jesusmaria Surquillo Ate
1.00
0.75
0.50
0.25
0.00
Barranco Sanjuandelurigancho Puentepiedra Chaclacayo Santiagodesurco Pueblolibre
1.00.04
0.75
0.50
0.25
0.00
Miraflores Santamariadelmar Villaelsalvador Puntahermosa Lince Lurin
1.00
0.75
0.05.02
0.25
0.00
Pucusana Lavictoria Pachacamac Carrabayllo Lurigancho Brena
1.00
0.75
0.50
0.25
0.00.00
J0a.0n Mar May Jul Sep Jan M0.a2r May Jul Sep Jan Mar M0.a4y Jul Sep Jan Mar May 0J.u6l Sep Jan Mar May Jul S0.e8p Jan Mar May Jul Sep 1.0
CGDN
Fig 6. Average variation of purchase category composition. Stationary vectors of the
mobility Markov chain models were used as input and were built from four weeks of
consumption by a week for the normalized discounted cumulative gain (NDCG) gain for
all individuals living in a given district.
August 12, 2020 8/28

|     |     | Merchant | network | resilience |     |     |     |     |
| --- | --- | -------- | ------- | ---------- | --- | --- | --- | --- |
It is well known that the distribution of the purchases is a highly skewed distribution
(Zipf-like distribution) toward certain purchase categories [15,25], where food-related
categories are the the dominant categories (see Fig. 3). With such a highly skewed
distribution, it may not always be easy to detect variations in the empirical distribution
due to the fact that certain categories are hidden in the tail of the distribution. Even if
the divergence metric display a clear sign of a shift in the distribution, to avoid these
pitfalls, we use a different approach and analyzed the microscopic dynamic of each
merchant during the ENSO events. Specifically, we analyzed the merchant dynamic
during the ENSO events, studied the ranking evolution of individual merchants through
the analysis of the discrete evolution of their PageRank in the transaction graph.
Additional information on the preprocessing of the transaction graph is provided in the
PageRank section. The transaction graph (see Fig. 7) is an aggregation of the
transaction records into a weighted and directed graph. Based on the transaction graph,
we computed the PageRank of the node in the resulting directed and weighted graph.
|     |     | a   |                                              | Sequ e n ce   o f  p r u c h ase  | Seq u e n c e  o f   p r u c h | ase  |     |     |
| --- | --- | --- | -------------------------------------------- | --------------------------------- | ------------------------------ | ---- | --- | --- |
|     |     |     | client                                       | b e tw e e n   [t , t [           | b e t w e e n   [ t , t 6[     |      |     |     |
|     |     |     |                                              | 1 8                               | 8 1                            |      |     |     |
|     |     |     | client i                                     | (t1, A), (t3, B), (t7, C)         | ...                            |      |     |     |
|     |     |     | client j (t2, C), (t4, D), (t5, A), (t7, B)  |                                   | ...                            |      |     |     |
|     |     | b   |                                              |                                   |                                | c    |     |     |
|     |     |     |                                              | merchant C                        |                                | C    |     |     |
client i
client j
|     |     |     |            |     |            | w=1 | w=1 |     |
| --- | --- | --- | ---------- | --- | ---------- | --- | --- | --- |
|     |     |     |            |     |            | B   | D   |     |
|     |     |     | Merchant B |     | Merchant D |     |     |     |
|     |     |     |            |     |            | w=2 | w=1 |     |
client i
client j
|     |     |     |     |     | client j | A   |     |     |
| --- | --- | --- | --- | --- | -------- | --- | --- | --- |
merchant A
|     |     | Fig 7.       |     | a)              |           | b)             |          |     |
| --- | --- | ------------ | --- | --------------- | --------- | -------------- | -------- | --- |
|     |     | Transactions |     | graph. Purchase | sequences | Users purchase | sequence |     |
represented as directed graph. c) Users purchase sequence represented as directed
Weight graph, where the weights represent the number of transaction made during a
|     |     | given time | slice between | two merchant. |     |     |     |     |
| --- | --- | ---------- | ------------- | ------------- | --- | --- | --- | --- |
To analyze the ranking evolution of each merchant, we split the transaction graph
into time slices =[G ,G ,G ,...]. Computation of the PageRank for each time
|     |     |     | G   | t0 t1 t2 |     |     |     |     |
| --- | --- | --- | --- | -------- | --- | --- | --- | --- |
slice enabled us to create a time series r (t) that represented the temporal evolution of
i
the ranking of each merchant i. In Fig. 12, we provide several examples of the
PageRank evolution for different merchant categories. Finally, we clustered the time
series r (t) using the kmeans algorithm once we transform each the time series using a
i
symbolization technique for time series (1d-SAX). Additional information on the
clustering method is provided in the Method section. As a result, six distinct profiles
patterns (see Fig. 8) emerged that highlighted different response profiles as a function of
|     |     | the merchant | category | and area during | the ENSO | events. |     |     |
| --- | --- | ------------ | -------- | --------------- | -------- | ------- | --- | --- |
In Fig. 9(a), we illustrate the distribution of the merchant categories in each cluster.
Our main findings are summarized in Table 1. First, The cluster #5 is a cluster of
| August | 12, 2020 |     |     |     |     |     |     | 9/28 |
| ------ | -------- | --- | --- | --- | --- | --- | --- | ---- |

<<<<llllaaaatttteeeexxxxiiiitttt    sssshhhhaaaa1111____bbbbaaaasssseeee66664444====""""tQLYLmOH1eiL4toqkL9yqPLeVIuMgY3PtD4k6bKVo/FvrW6TL/fPzenGrj4rcMYDjBsEjf13p78j/M0y3gsOX9SoSUeJAeI9B3O14wBW0gkE===="""">>>>AAAAAAAAAAAAEEEEBABB33n3iiiiccccjjjjZZZZLLLLPNPNbbTbttttNNtNAAAAEEEEMMMMbfbfHHHHNNuNdRCRA808Sl0l/f/fjDUDSSOSFFAFIYYIwy6wd8VdWrqWpU1pEqVEhQAhBgpBSNlaqZZiKFLL1tIbKiDKQkigIBCIJCQJISKIVBiVVVTVwcUw4OX4VBnVgaogkJEk0ti0lJQlZWBZKSSKoqEosLispLFpeX7ebkvT53Q9KRkKVlrVHxOHd77dtbataW1araXr01o0FAMFtbgtl5ylCYrCsLEsSESS7u774y44LBLLExUEioUiYu1YoLGorKvrjgvj8/A8EAZEbGvbl5QlLSNLd2+dgYigZ2MZmTxuMhsODqnopSKhb2oNRnUKlL2WoRXjykcZTnvLf+28f+79v5DzO/e+bf//2zbmZM3Zm6Z11snZwHbOzRTyxW+pRpNShKZVeoKRH3Yr8ndPu/5+7X9+PKamiWasX3surB5Nls8e638ubbf3X9T7X1aite/5ev8eutLqPOztG40xze4+V+u8u/W73+rd1g1e5542sXvvbmlNd6p93sefaOWuLdD7rMLZNqMVR+k5C0Vp9xFikJyTW722WMeZZ0RpH1I7ozkn/v6eDR8jAWr8qG1IZJMSqqRUFcD5TqIV2wWhjZLzT5SyKR1iJJ1T3cJ4MaIn+/561QShDGJMGEbZZ6yxhiBEIFHKvH4efel5CjDF+5PyBC/RX3xuFHMO9d+79zc35+N1JiTAXLoXalTagWKoseZ8ffxeWTP2sCv+OH6OcBPCzQBhm4XxandOB4gwZTdnNheGUTPmjIZRZyUkUV9qIDyGDQThF96qobNyH+0DGqvd8rGe7MSf929RYi7ISHfMgCiKnsixKsLypq+q0lOZbRhGFylJRVuc/GFelhFFSpKkpKrqhknbS0OSyzlOwkRBVRiOrjxNDEUQCOiaMvdzdwQDvk3jG2h6fhmLt3rdrg1CtgpT/3sahv19jq5p1ew6ihOL30rTyR1E9N1Wqtn2cnVfx0pRMTadBcC8MHtclSTKYiypgYQl7bPszwaCBh8n77wv77ssQWuKsm64tM13o8Ex9f08LLPOwU0Wmg4Ce/I9QVdM1N096QJAHP20dPKQbswn1nx+/K9ioU1Yn5Fo+RyzqJW1lpniogRJhNMMRLEBPmLxvMsfnX2S0akCjH1zXA2hsWbY/vsg4buiYqs9fB1vdO9Y9cvgjDg4FoOwT8p+S+uuwvywBQYqQ+IdpVHD9RZ5cZjZhHJlimjs4Mtfn/uYSxLT7ZE3NE4FIZCkDT0hhtYtIe5M59ENN9TbqR32PneP53HGJhqLt18W9l7Ic8qWU7iLIhN9s7I3y2iFjmDQUyub724Pdvdlx6xdU9XTGkG2zl57xL4xXgjHvqQnc/chLFM1ni96Z2jIWoDFe1w9J3CdVb2roeCJQPCmbIh6VERc2BjwsxNguJyBYCnhJDfyDhQkCAQFGocDCmCBDgSBAJIBSCBAUBDyMIDMAZgKM1MRJCQTKCECRCIKjVPGU9GkC+OTQuAxRCI9QDP84BM8GwrKcVzAA5agHQ4bn5IwDiIhISDT0pK8R0WjvkpQBpdpHGGZD0Ke2eKMNYmISQMMtYJ2mNIh4ymQhKLbA62kUKAU0QEUMiJELJfhdDTGEcmSShSmiHA9I7kDRHkvotPmBOFHvvRbjXD97bf2wkPsRZZ137xogr1z8lizpn7VNaULcbGmUEOy8md31nUpCpMl5PzJsTNStVu+8ljmJCqjQntIEgEFvCePxeCKoXtGzk0cGxMnTGnDznihESPNnfnmAJgkwqQ85w5Tj8hNZcTlppG7OWtZYZxyzvkuZewxey+e22NVsl5HrNVtkbJqnk/al3V3dsvJ77tvbpoRmPa/t+lQSoJfbre14jzbfUvU4hHmH1t5181BaA/o1BU4ZuGJudqPgfCealqqmL4vKcQAJjTX7/V5WzWvVeb35N4kNZJ8/D+imIb48z8Eeg+Rzp6vWZkLJ1VAgBDzD0DKMU7J/yZqsFMpDdDsAXxApgJ5n67PyWSJqVo+1e1sDpCq073l4Kfbm1G0qwiVS5S7m+mllL5zvMO8hVhMTIXZpYbWnqOhfFfC0OugxStVlxK5sjYrEi4GKmUOOuUKHSNauUY9kuoLIbDS4uzZxbCiqhu71nMusYuWJXXdnNFi1KOcPOz0TzpsOvk7bfZOUbTd9W2xjjZvZj6a6Jp+W57K4ZPkDk1lGlT2z/Pe+e7WxyO9JZkrLiKNmvTk04SKFfnfxeBlVVd0b0s6w3DHoEjX8E/eLC/QpR2w68RDMC3HOvtwYgIKjPI+g/QDC3L/eAo/g7FcW8/D8oAPvd/ixof9/KO24uDgWvP6b9w2Hnw9rdO19fmt7Bg9y+14t03F3tvrttbeY7G3bUxXvL19786cXMzu9yswsrfCnMCgoFp/Zj+h1ahMuNgbAMVTeT4pPfAiIw+TAF++2bgHP8ibvAlXG69gn28LsoEOAQ392fbAvSgDY+C6Qe+Xfxxx68CyIdCvJb7jw4jjP71fzx1ni+bBf4qPnXy3i9vs35l/Ptvvs7XVf79PnPqXQ6XG/Y9/uozz80b9ft6EuO2V1nfpyf48WMz56IR54zOAliaEQ3vv53wLd5r/+xMfH9CEUi9bcgYtrud0/w/T9c8sB<A9K/pAmlH=oaN=7t7<PeJ/Axsl=i=a<t<t/>/ellxaaitttee>xxiitt>>
<<llaatteexxiitt  sshhaa11__bbaassee6644==""KD4zFXnwkBTHikLbVa6Ta3Ug7dNpX7EPWyvZmyDCRzdZ425tpiGOIc=="">>AAAAAADDgg3niiccjjVVJLddTb9tsMwwFGLD11pZxBgobzdyBs2wU48u8umbKHtoTEOAqW01tVkVqKiKTQEBypaIkEB9Cx8w7OJSFSJ6KTyWCq1rFKUXqHcc2z2kIqlaTRSIL4HzAtUFHVV9fk7jI0/Zxbj7+CA9fx8TG41bZDx1AHdG+n36KMUk5xP+jcc7c5495i9fnkc7RjlMJZiKrWlDe4dJduO3w53q2/2f8uvnz1Fn64l2r7zj53avv0XHbD9zZebbGW24+/P2qqq6KJWWHXAAex85ykARpX5qEMkIc4VqZkicLlHcgDRLIXqUwm5TNgSsYljYSjLmMczSyYOO04wvNSdjPqzR5+HcWCYFkXiJ/I6v4+uiSTx0zsPxommUkeuzJXoEJ4HlijqzjRTR1Ro893RzjcFSOxRmzM5lV9Iorm0Zr6BVVkSu1txawiZSqVjrRjEBYMXVrfNWMXLtubtr48HT1vuGuDxdTLqmjsBPUDJB0jJpnYn8anZTWDXrVOXrYvjlLc+i8mieAzN8uk8Ax4K6Pz3EVlZfzd/1+jt4eWD+k12qLaxlI4ckZYjphSRJ4q/Zm42stt7o3PQtUpZUgknSSexbsK5ybjb6WN9mvKm+cgGFedwrpC8bCI9HpSggxB2THfR2uiouEYRFJxFkAhAQhgxKpPmGgHJACID5INpOxEBMBEBSVqd6QR/gDgBRgo5CKR4uMgcgyVJxki4pSCE0qdSYMEsloGEunSetmSlSRVIIiEoRjGYbl0Jn5NTGmsg50Ftjmc95NqcbZz1MbqG6zOWam2VSj0Ga53JITygfbCvMyPVAOXQpTFhGLGWzqGzrFPT1r20i2YybZ9vk+/UZPCT5etZpe9mn+ZXK97I95htl1zoYxnYVBOWCfbE2/Xs7t53rr5/fx/f6nT+C58FawUQ7Qy+1mPxU4jEq9qVbQSaMR6nYf6H7blUNpqteTiktXkv5n+D63kqrSTlQFkClScZQzYGnCVdFUelEYuWX6Vce9n+zfOMzjnKscry2vbesu4z2jsUvzU9LxqizgS1sqm+XfOcnarmXuH45/1W+t73MeDglcKpcXwIfHw+CB4fax8ffP//ChbTYc7B/Tf0C/QbWA/fwfugdv/aae//evB2+Zh1gi0F8LwXVgOH0H6fYrui/Ow7SA4H+XY+QE9QDBcsMC/dzhntnNuxBfFC/drwrV/9kysP/b9uFC9G9Pl66U5N5xz3voM2YYKW8mN4/ud3weXorfUMMTSmv<<//llaatteexxiitt>>
merchants that experienced a drop in their ranking during the ENSO events in February.
Here, we observed an overrepresentation of gas stations and food related merchants. In
contrast, for cluster #2, where merchants experienced a surge in their ranking during
the ENSO events in February, we observed an overrepresentation of health related
merchants and gas stations. These results can be explained as follows: some gas stations
experienced shortages, and there was a surge in the demand for health related products.
Fig 8.
|     |     | Time | series clustering. |     |     |     |     |
| --- | --- | ---- | ------------------ | --- | --- | --- | --- |
Table 1. Summary of most important merchant categories found in each cluster
|     |     | cluster ranking |        |                        |     | under represented | categories |
| --- | --- | --------------- | ------ | ---------------------- | --- | ----------------- | ---------- |
|     |     |                 | over   | represented categories |     |                   |            |
|     |     | #0              | health |                        |     | food              |            |
0
|     |     | #1  | gas, | clothing |     | unlabeled stores |     |
| --- | --- | --- | ---- | -------- | --- | ---------------- | --- |
0
|     |     |     | health, | gas, technology, | trans- |      |     |
| --- | --- | --- | ------- | ---------------- | ------ | ---- | --- |
|     |     | #2  |         |                  |        | food |     |
ports
0
|     |     | #3  | health |     |     | food |     |
| --- | --- | --- | ------ | --- | --- | ---- | --- |
0
|     |     | #4  | food, | gas |     | health, clothing |     |
| --- | --- | --- | ----- | --- | --- | ---------------- | --- |
0
|     |     | #5  | gas, | food |     | clothing, night-life |     |
| --- | --- | --- | ---- | ---- | --- | -------------------- | --- |
0
In Fig. 9, two additional phenomena can be observed: first, an increase in insurance
purchases after the first event in February (cluster 3), and second, an increase in
purchases of technology related items during first event (cluster 2). We observe a surge
in the purchased of new insurance policies after the first event. It should be noted that
Peru is an underinsured country (only approximately three in hundred houses are
insured), and in the aftermath of the event it appears that people decided to purchase
new insurance policies. With respect to technology-related items, a query to the
database at our disposal revealed that no transaction were made in that category from
February 15 to 19, 2017. We observed a shift in purchases after February 19. This
|     |     | behavior appear | to be due | to the purchases | of prepaid | cell phone plans. |     |
| --- | --- | --------------- | --------- | ---------------- | ---------- | ----------------- | --- |
We note that people’s response to the crisis were very heterogeneous in time, space
and behavior. We believe that the microscopic approach developed in this study is a key
methodological innovation that helpful for fully understanding the extent of a crisis and
| August | 12, 2020 |     |     |     |     |     | 10/28 |
| ------ | -------- | --- | --- | --- | --- | --- | ----- |

a
|     |     |     |     | Cluster#0 |     | Cluster#1 |     |     | Cluster#2 |     |
| --- | --- | --- | --- | --------- | --- | --------- | --- | --- | --------- | --- |
50
)%(rorre∆
0
−50
100
10−1
10−2
10−3
|     |     |     |     | Cluster#3 |     | Cluster#4 |     |     | Cluster#5 |     |
| --- | --- | --- | --- | --------- | --- | --------- | --- | --- | --------- | --- |
50
)%(|rorre∆|
0
−50
100
10−1
10−2
10−3
|     |     |     | dooF delebalnU | htlaeH gnihtolC saG ygolonhceT .snarT gnisuoH ecnarusnI sletoH efiLthgiN | dooF saG | htlaeH delebalnU gnihtolC | sletoH efiLthgiN ygolonhceT .snarT | dooF saG | htlaeH delebalnU gnihtolC efiLthgiN | ygolonhceT .snarT sletoH gnisuoH |
| --- | --- | --- | -------------- | ------------------------------------------------------------------------ | -------- | ------------------------- | ---------------------------------- | -------- | ----------------------------------- | -------------------------------- |
b
|     |     |     | 100 | Cluster#0 |     | Cluster#1 |     |     | Cluster#2 |     |
| --- | --- | --- | --- | --------- | --- | --------- | --- | --- | --------- | --- |
)%(rorre∆
0
−100
100
10−1
10−2
10−3
|     |     |     |     | Cluster#3 |     | Cluster#4 |     |     | Cluster#5 |     |
| --- | --- | --- | --- | --------- | --- | --------- | --- | --- | --------- | --- |
100
)%(srorre∆
0
−100
|     |     |     | 100                                                           |                                                                                                                                                                                                                                            |                            |                                                                           |                                                                     | 100                                                           |                                                                                                                     |                                                                                                                               |
| --- | --- | --- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
|     |     |     | 10−1                                                          |                                                                                                                                                                                                                                            |                            |                                                                           |                                                                     | 10−1                                                          |                                                                                                                     |                                                                                                                               |
|     |     |     | 10−2                                                          |                                                                                                                                                                                                                                            |                            |                                                                           |                                                                     | 10−2                                                          |                                                                                                                     |                                                                                                                               |
|     |     |     | 10−3                                                          |                                                                                                                                                                                                                                            |                            |                                                                           |                                                                     | 10−3                                                          |                                                                                                                     |                                                                                                                               |
|     |     |     | seroflariM ajroBnaS ocruSeDogaitnaS ordisInaS raMleDaneladgaM | erbiLolbeuP amiL leugiMnaS aniloMaL cnagiruLeDnauJnaS olliuqruS airaMsuseJ etA ecniL sollirrohC ocnarraB airotciVaL serroPeDnitraMnaS roflariMeDnauJnaS aicnednepednI sovilOsoL camiR ardeiPetneuP anerB atinAatnaS samoC niruL onitsugAlE | sa e r j r o c o r d r a M | e r b a m l e u a n c n o l l a i r e tc A e ln so o c a i r s e r        | ar o fl i c s o v c a m a r d a n a t i c a m s i u s a m n i r o n | seroflariM ajroBnaS ocruSeDogaitnaS ordisInaS raMleDaneladgaM | erbiLolbeuP amiL leugiMnaS aniloMaL cnagiruLeDnauJnaS olliuqruS airaMsuseJ etA ecniL sollirrohC ocnarraB airotciVaL | serroPeDnitraMnaS roflariMeDnauJnaS aicnednepednI sovilOsoL camiR ardeiPetneuP anerB atinAatnaS camacahcaP siuLnaS onitsugAlE |
|     |     |     |                                                               |                                                                                                                                                                                                                                            | o fl a o B r u S i s I l e | ii L o L g i M i l o M ai g i r u q r a M ii L l r rr ori n a o t c r o P | a r i M n e d i l O i R e Bi P e r n A a c L n o C u Ls i t u       |                                                               |                                                                                                                     |                                                                                                                               |
|     |     |     |                                                               |                                                                                                                                                                                                                                            | r i M n a S e D n a S D a  | l b e n aL a u L e u uS s s e h C a B V a e D                             | ep n e s o L e t n a t n a a h c a S g A l                          |                                                               |                                                                                                                     |                                                                                                                               |
|     |     |     |                                                               |                                                                                                                                                                                                                                            | o g a n e l a              | u P S D n J L n i t r                                                     | D nn e d e u P S a P E                                              |                                                               |                                                                                                                     |                                                                                                                               |
|     |     |     |                                                               |                                                                                                                                                                                                                                            | i t n a d g a              | a u J a M                                                                 | Ia u J                                                              |                                                               |                                                                                                                     |                                                                                                                               |
|     |     |     |                                                               |                                                                                                                                                                                                                                            | S M                        | n a nn aa SS                                                              |                                                                     |                                                               |                                                                                                                     |                                                                                                                               |
S
Fig 9. Proportion of merchant categories/area inside different clusters. a) Proportion
of merchants per cluster as a function of their Classification of Individual Consumption
According to Purpose (COICOP), b) Proportion of merchants per cluster as a function
of their district area. The top of each figure indicates the relative differences between
the proportion of a given category inside a cluster and the proportion of that category
in our dataset.
|        |          | the | societal outcome | of an event. |     |     |     |     |     |       |
| ------ | -------- | --- | ---------------- | ------------ | --- | --- | --- | --- | --- | ----- |
| August | 12, 2020 |     |                  |              |     |     |     |     |     | 11/28 |

|     |     | Table | 2. Standard | score | of core size V | (t) at various | event times |     |     |
| --- | --- | ----- | ----------- | ----- | -------------- | -------------- | ----------- | --- | --- |
c
|     |     |     |     |      | |             | |          |     |     |     |
| --- | --- | --- | --- | ---- | ------------- | ---------- | --- | --- | --- |
|     |     |     |     | date | V (t) z-score | event type |     |     |     |
c
|     |     |            |             |     | | |      |                 |              |          |     |
| --- | --- | ---------- | ----------- | --- | -------- | --------------- | ------------ | -------- | --- |
|     |     |            | 2017/02/20  |     | 27 -2.44 | ENSO event      | mid-Feb      |          |     |
|     |     |            | 2017/03/24  |     | 38 -1.79 | ENSO event      | end of March |          |     |
|     |     |            | 2017/04/07  |     | 41 -1.61 | ENSO event      | beginning    | of April |     |
|     |     |            | 2017/04/11  |     | 97 1.67  | Easter vacation |              |          |     |
|     |     |            | 2017/05/17  |     | 154 5.02 | Mother’s        | day          |          |     |
|     |     | Resilience | transaction |     | graph    |                 |              |          |     |
The presence of a core/periphery structure in networks is an indication that the overall
network structure is resilient to the random removal of some nodes [26,27]. By
exploring the transaction graph, we observed that a very small core of merchants
(constituted of less than 1% of merchants) was almost fully connected and surrounded
by a vast periphery that was connected to the core in a tree-like manner. The
merchants belonging to the core structure were often large supermarkets that provide a
vast array of goods including basic necessities. To monitor the size of the core network
structure over time, we computed the temporal evolution of the size of the core
structure of the transaction graph at each time slice =[G ,G ,G ,...]. To derive
|     |     |     |     |     |     |     | G t0 t1 | t2  |     |
| --- | --- | --- | --- | --- | --- | --- | ------- | --- | --- |
the size of the core structure, we used the method developed by Ma et al. [28] (see
Materials and Methods section for more detailed information), a method designed to
detect the core/periphery structure for a directed and weighted graph. In the
supporting information, we also provide the results that exploit a different approach
with the k-core decomposition algorithm. Our mains findings are summarized in
Fig. S4 a we explore the dynamic of the transaction graph. In Fig. S4 b we see that the
node that belongs to higher core concentrates a higher proportion of the transactions
|     |     | than nodes | in lower | cores. |     |     |     |     |     |
| --- | --- | ---------- | -------- | ------ | --- | --- | --- | --- | --- |
As previously demonstrated, ENSO events impacted the buying people’s buying
patterns; however in Fig. 10 we also demonstrate that these events significantly
impacted the size of the core structure V (t) of the transaction graph. Our main
c
| |
finding is that the core size distribution is similar to normal to normal distribution. We
calculated the Kolmogorov-Smirnov (KS) distance between the core size distribution
V (t) and normal distribution (68,17), and the KS-test produced =0.09 and
c
|     |     | | | |     |     | ∼N  |     |     | D   |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
p-value=0.19. Nonetheless, despite relative accordance with the normal distribution
the core size distribution shows in Fig. 10b demonstrates extremes values at both tails
that deviate from the normal distribution. In table 2, we display the list of noticeable
events with their standard scores. Our results reveal that for both ENSO events in
mid-Feb and mid-March the core size significantly decreased from the usual behavior
compared to Mothers’ Day, or Easter (two particularly popular holidays in the Peruvian
culture) where the core size significantly increased. In Fig. 10(d) we see the changes in
the category distribution of merchants present in the core during both events (the
February event and the March event). During these events only a subset of the
merchant’s categories remain present in the core. Health and food related merchants are
|     |     | the main   | remaining | categories. |            |     |     |     |     |
| --- | --- | ---------- | --------- | ----------- | ---------- | --- | --- | --- | --- |
|     |     | Discussion |           | and         | Conclusion |     |     |     |     |
In this study, we explored the impact of the ENSO events of 2017 on retail sales
through the lens of a massive transaction dataset from the greater area of Lima, Peru to
| August | 12, 2020 |     |     |     |     |     |     |     | 12/28 |
| ------ | -------- | --- | --- | --- | --- | --- | --- | --- | ----- |

|     |     | a   |     | b   | d    |       |     |     |
| --- | --- | --- | --- | --- | ---- | ----- | --- | --- |
|     |     |     |     |     | Food | 20-02 |     |     |
22-02
Mother’s day
|     |     |     |     |     | Unlabeled | 24-03 |     |     |
| --- | --- | --- | --- | --- | --------- | ----- | --- | --- |
26-03
|     |     |     | Easter |     | Gas    |     |     |     |
| --- | --- | --- | ------ | --- | ------ | --- | --- | --- |
|     |     |     |        | c   | Health |     |     |     |
Insurance
Technology
Clothing
|     |     |                    | E N S O     |   ev e n t   | Housing |      |      |     |
| --- | --- | ------------------ | ----------- | ------------ | ------- | ---- | ---- | --- |
|     |     | EN S O   e v e nt  | e n d  o f  | M a r c h    |         |      |      |     |
|     |     | m i d - F e b      |             |              | Trans.  |      |      |     |
|     |     |                    |             |              | 10−3    | 10−2 | 10−1 | 100 |
Fractionofmechantinthecoreineachcategory
Fig 10. Evolution of the core structure of the transaction graph over time. a)
Temporal evolution of the size of the core structure of the transaction graph. b)
Boxplot of the core size distribution. c) Core size distribution approximated by kernel
density estimation. d) Fraction of merchants that belong to the core nodes split by
categories, the diamond represents the category split during the first ENSO event of
|     |     | February, | whenever the | square represents | the second | event of end of | March. |     |
| --- | --- | --------- | ------------ | ----------------- | ---------- | --------------- | ------ | --- |
understand how the population handled the aftermath of the climatic events. At the
macroscopic level, despite a clear slowdown of economic activities triggered by the two
main ENSO events occurring in February and March, we demonstrated that the overall
economic activity recovered swiftly from the events (see Fig. 3). The second event
appears to have had less impact on the economic activities than the first event,
although its intensity was not smaller. A more detailed analysis of the events indicated
that regions that registered more damage induced by the events also suffered from a
long-term deficit of consumption compared with other areas (see Fig. 5). We quantified
howindividualpurchasecategoriesandfrequentlocationschangedduringtheevents(see
Fig. 6),demonstrating that there was a transient period during which people changed
their purchase sequences to accommodate new necessities or constraints. By tracking
the ranking evolution of each small business in the transaction graph, we revealed that
small businesses were impacted very differently based on their category. A subset of
merchants, such as pharmacies, hospitals, gas stations and grocery stores exhibited a
surge of activity during the events. In contrast, merchants that sold non-necessities
experienced a drop in their ranking during the events. In addition, by studying the core
network structure of the transaction graph, we observed a clear reduction in the size of
the core network structure during both events,which is in contrast with other types of
events, such as Easter or Mother’s Day, where the core structure increased in size.
We analyzed different small subsets of merchants in various districts to evaluate
alternative explanations for the slowdown of sales, such as failure of point-of-sale
systems and problems in the payment architectures. However, none of the analyzed
merchants experienced these problems. Nevertheless almost all merchants encountered
severe problems with the water supply during the events. We also asked merchants
about the decrease in the number of clients during the two events of the El Nin˜o
phenomenon in 2017. The responses were the same: the number of customers did not
decrease, and the usual number of employees attended. We believe that this was due to
the fact that the vital infrastructure in inner Lima did not suffer significantly during the
event.
Despite the strength of the event, Peruvian society continued its activities due to the
economic structure and the manner in which the population faced the event. One
explanation is that Peruvian society is used to periodic climatic events that occur on a 2
|        |          | - 4 year basis, | although | the 2017 event | was stronger | in intensity. |     |       |
| ------ | -------- | --------------- | -------- | -------------- | ------------ | ------------- | --- | ----- |
| August | 12, 2020 |                 |          |                |              |               |     | 13/28 |

We believe that beyond the case of the ENSO phenomenon, the methodological tools
designed and developed in this study can help further understand the microscopic
dynamics that underpin the societal outcome of climatic events. We believe that our
approach based on the microscopic analysis of consumption patterns can help build
information systems in order to aid the population during the relief effort period of a
climatic event or other type of societal shock. However, this microscopic approach may
raise privacy leaks [29] that need to be further addressed by applying privacy techniques
such as in [30,31], while minimizing the impact of privacy techniques on the relevance of
our study.
|     |     | Materials   | and     | Methods |     |     |     |     |
| --- | --- | ----------- | ------- | ------- | --- | --- | --- | --- |
|     |     | Transaction | dataset |         |     |     |     |     |
This dataset was gathered from June 2016 to May 2017, containing approximately 1.5
million clients, 55,000 distinct merchants, and 116.8 million transactions from both
credit and debit cards in Peru. These data are associated with customer consumption
|     |     | registered  | by credit   | and debit | cards in stores | located   | in Peru. |     |
| --- | --- | ----------- | ----------- | --------- | --------------- | --------- | -------- | --- |
|     |     | The dataset | is composed | of        | the following   | features: |          |     |
1. Features describing the clients such as anonymous ID, age, gender, and country in
|     |     | which | the card | was issued. |     |     |     |     |
| --- | --- | ----- | -------- | ----------- | --- | --- | --- | --- |
2. Features describing the transaction, such as the timestamp, amount spent in
|     |     | Peruvian | currency, | and the | number | of transactions. |     |     |
| --- | --- | -------- | --------- | ------- | ------ | ---------------- | --- | --- |
3. Features associated with the bank agency, namely the region, province, and
|     |     | district, | in which | the agency | of the | client was located. |     |     |
| --- | --- | --------- | -------- | ---------- | ------ | ------------------- | --- | --- |
4. Features characterizing the merchants, such as merchant ID, merchant name,
merchant address, the MCC [20] and the Lambert coordinates of the merchants.
In this study, we merged the MCC categories into a more meaningful categorization,
often used in microeconomics [32], namely, Classification of Individual Consumption
According to Purpose COICOP [33]. The COICOP aims to divide individual
|     |     | consumption      | expenditures | into       | 15 categories, | as depicted | in Table 3. |     |
| --- | --- | ---------------- | ------------ | ---------- | -------------- | ----------- | ----------- | --- |
|     |     | Kullback–Leibler |              | divergence | (KLD)          |             |             |     |
To analyze buying patterns, we used the KLD defined in (1) to compute the two
|     |     |     |     |     | (1) | (2). |     |     |
| --- | --- | --- | --- | --- | --- | ---- | --- | --- |
different divergence measures and The KLD is a general measure of
|     |     |     |     | D   | D   |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
dissimilarity between two probability distributions. In (2), we define (1) as the KLD
D
|     |     |     |     |     |     |     | S(t) | S(t) |
| --- | --- | --- | --- | --- | --- | --- | ---- | ---- |
between the probability distribution of the share of purchases (k), where (k) is
|     |     |     |     |     |     |     | i   | i   |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
the share of total expenditures allocated to expenditure category k [1,2,...,K] and
|     |     | K   |     |     |     |     | ∈ i | t.  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
is the total number of COICOP expenditure categories, in region at time Thus,
S(t) (k)=(s ,s ...,s ) denotes the vector of the expenditures shares in each category
|     |     | i   | i1 i2 | ik  |     |     |     |     |
| --- | --- | --- | ----- | --- | --- | --- | --- | --- |
i, [t,t+w].
made by individuals living in district area during the time interval We
compared it with the average share of purchases in each COICOP category for all
transactions in our dataset S¯(k), which represents the average behavior of a consumer
throughout the country. Finally, if a substantial divergence suddenly appeared in our
dataset, we considered it a change in the consumption pattern of an individual living in
the particular area. In this study, we limited the geographic area to the 42 districts of
Lima. In (3), we define the divergence measure (2) as the average KLD between S(j)
i
D
| August | 12, 2020 |     |     |     |     |     |     | 14/28 |
| ------ | -------- | --- | --- | --- | --- | --- | --- | ----- |

Table 3. Classification of Individual Consumption According to Purpose (COICOP)
|     |     | Code | Name         |                   |                   |             |     |                   |       |           |             |          |     |
| --- | --- | ---- | ------------ | ----------------- | ----------------- | ----------- | --- | ----------------- | ----- | --------- | ----------- | -------- | --- |
|     |     | 01   | Food         | and non-alcoholic |                   | beverages   |     |                   |       |           |             |          |     |
|     |     | 02   | Alcoholic    | beverages,        |                   | tobacco     | and | narcotics         |       |           |             |          |     |
|     |     | 03   | Clothing     | and               | footwear          |             |     |                   |       |           |             |          |     |
|     |     | 04   | Housing,     | water,            | electricity,      |             | gas | and other         | fuels |           |             |          |     |
|     |     | 05   | Furnishings, |                   | household         | equipment   |     | and routine       |       | household | maintenance |          |     |
|     |     | 06   | Health       |                   |                   |             |     |                   |       |           |             |          |     |
|     |     | 07   | Transport    |                   |                   |             |     |                   |       |           |             |          |     |
|     |     | 08   | Information  |                   | and communication |             |     |                   |       |           |             |          |     |
|     |     | 09   | Recreation,  |                   | sport             | and culture |     |                   |       |           |             |          |     |
|     |     | 10   | Education    | services          |                   |             |     |                   |       |           |             |          |     |
|     |     | 11   | Restaurants  |                   | and accommodation |             |     | services          |       |           |             |          |     |
|     |     | 12   | Insurance    | and               | financial         | services    |     |                   |       |           |             |          |     |
|     |     | 13   | Personal     | care,             | social            | protection  |     | and miscellaneous |       | goods     | and         | services |     |
14 Individual consumption expenditure of non-profit institutions serving households
|     |     | 15               | Individual | consumption |       |              | expenditure | of      | general | government  |     |              |     |
| --- | --- | ---------------- | ---------- | ----------- | ----- | ------------ | ----------- | ------- | ------- | ----------- | --- | ------------ | --- |
|     |     | the distribution |            | of the      | share | of purchases |             | at time | j       | in district | j   | and S(k) the |     |
i
|     |     |              |     |       |              |     |           | k        |          | j        | w        |     |     |
| --- | --- | ------------ | --- | ----- | ------------ | --- | --------- | -------- | -------- | -------- | -------- | --- | --- |
|     |     | distribution | of  | share | of purchases |     | at time   | in       | district | over     | days.    |     |     |
|     |     |              |     |       |              |     |           |          |          | (cid:20) | (cid:21) |     |     |
|     |     |              |     |       |              |     |           | (cid:88) |          | P(k)     |          |     |     |
|     |     |              |     |       | KLD(P        |     | Q)=       | P(k)     | log      |          |          |     | (1) |
|     |     |              |     |       |              |     | (cid:107) |          |          | 2 Q(k)   |          |     |     |
k∈K
|     |     |     |     |     |        | (1)    | (j)=KLD(S(j) |            |     | S¯)         |     |     |     |
| --- | --- | --- | --- | --- | ------ | ------ | ------------ | ---------- | --- | ----------- | --- | --- | --- |
|     |     |     |     |     |        |        |              |            | i   |             |     |     | (2) |
|     |     |     |     |     |        | D(i,w) |              |            |     | (cid:107)   |     |     |     |
|     |     |     |     |     |        |        | 1            | (cid:88) w |     |             |     |     |     |
|     |     |     |     |     |        | (2)    |              | KLD(S(j)   |     | S(k+d)      |     |     |     |
|     |     |     |     |     |        | (j)=   |              |            |     |             | )   |     | (3) |
|     |     |     |     |     | D(w,i) |        | w            |            | i   | (cid:107) i |     |     |     |
d=1
|     |     | Causal | impact |     |     |     |     |     |     |     |     |     |     |
| --- | --- | ------ | ------ | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
Causal impact captures causality by measuring the difference between two different
time series: one series under treatment, and another series not under treatment.
Therefore, the causal inference algorithm takes three parameters: 1) the observed o time
T(t)
series (k)), where k [1,2,...,K] is the total number of COICOP expenditure
o,i
∈
categories, in region i within period t; 2) a control time series c T(t) (k)): and 3) an
c,i
intervention date d, which is February 15, 2017, the start date of the El Nin˜o
phenomenon. The first step is to train a statistical or machine learning model, using
parts of the time series before the intervention date (i.e., pre-period) to learn how to
explain the studied time series T(t) (k) as a function of the control time series T(t) (k).
|     |     |     |     |     |     |     | o,i |     |     |     |     |     | c,i |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
Then, the learned model is used to predict the behavior of the studied time series after
the intervention date (i.e., post-period), which provides the contrafactual estimate.
Finally, the algorithm measures the difference between the predicted and real-time
series to capture causal impact. It is worth noting that the model used in this study is
|        |          | the Bayesian | structural |     | time-series |     | model | [23]. |     |     |     |     |       |
| ------ | -------- | ------------ | ---------- | --- | ----------- | --- | ----- | ----- | --- | --- | --- | --- | ----- |
| August | 12, 2020 |              |            |     |             |     |       |       |     |     |     |     | 15/28 |

|     |     | Individual |                                 | stationary |     | purchasing |     | behavior |     |     |     |     |     |
| --- | --- | ---------- | ------------------------------- | ---------- | --- | ---------- | --- | -------- | --- | --- | --- | --- | --- |
|     |     |            | A user, merchant, day, category |            |     |            | B   |          |     | C   | D   |     |     |

Bob, merchant 1, 1, coicop 3
|     |     |     | Bob, merchant 5, 1, coicop 4 |     |     |     |     | 0.4 |     | 0.4 |     | 0.5 | COICOP 1 |
| --- | --- | --- | ---------------------------- | --- | --- | --- | --- | --- | --- | --- | --- | --- | -------- |
Bob, merchant 2, 1, coicop 1
|     |     |     |     |     |     |     |     | 0.4 |     | 0.2 |     | 0.2 | COICOP 2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | -------- |
0.2
|     |     |     |                                       |     | ..  |     |     | 0.2 0.3 |     |          |     | 0.2 | COICOP 3 |
| --- | --- | --- | ------------------------------------- | --- | --- | --- | --- | ------- | --- | -------- | --- | --- | -------- |
|     |     |     |                                       |     |     |     | 0.5 |         | 0.3 |          |     |     |          |
|     |     |     |                                       |     |     |     | 0.4 |         |     | 0.7 0.1  |     | 0.1 |          |
|     |     |     | Bob, merchant 1, 7, coicop 3          |     |     |     |     |         |     |          |     |     | COICOP 4 |
|     |     |     | 1-t keew Bob, merchant 2, 7, coicop 1 |     |     |     |     | 1       |     |          |     |     |          |
0.1
|     |     |     | Bob, merchant 81, 8, coicop 2 |     |     |     |     | 0.5 |     |     |     |     |     |
| --- | --- | --- | ----------------------------- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|     |     |     | Bob, merchant 23, 8, coicop 1 |     |     |     |     | 0.3 |     |     |     |     |     |
1-T
....
0.4
|     |     |     | Bob, merchant 81, 14, coicop 2 |     |     |     |     |     |      | 0.3  |     | 0.4  | COICOP 1 |
| --- | --- | --- | ------------------------------ | --- | --- | --- | --- | --- | ---- | ---- | --- | ---- | -------- |
|     |     |     | Bob, merchant 23, 14, coicop 1 |     |     |     |     | 0.4 |      |      |     |      |          |
|     |     |     | t keew                         |     |     |     |     |     |      | 0.2  |     | 0.2  |          |
|     |     |     | Bob, merchant 1, 15, coicop 3  |     |     |     |     |     | 0.35 |      |     |      | COICOP 2 |
|     |     |     | Bob, merchant 5, 15, coicop 4  |     |     |     | 0.2 | 0.3 |      |      |     |      |          |
|     |     |     |                                |     |     |     |     |     |      | 0.15 |     | 0.15 | COICOP 3 |
|     |     |     | Bob, merchant 2, 15, coicop 1  |     |     |     | 0.5 | 0.3 | 0.4  |      |     |      |          |
|     |     |     |                                |     |     |     | 0.4 |     | 0.65 |      |     |      |          |
|     |     |     |                                |     |     |     |     | 1   |      | 0.15 |     | 0.15 | COICOP 4 |
0.3
|     |     |     |     |     | ..  |     | 0.5 |     |     | 0.1  |     |     |           |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---- | --- | --- | --------- |
|     |     |     |     |     |     | T   |     |     |     |      |     | 0.1 | COICOP 12 |
0.3
|     |     |     | Bob, merchant 1, 21, coicop 3 1+t keew |     |     |     |     |     |     | 0.1  |     |     |     |
| --- | --- | --- | -------------------------------------- | --- | --- | --- | --- | --- | --- | ---- | --- | --- | --- |
Bob, merchant 1, 21, coicop 3
Bob, merchant 42, 21, coicop 12
|     |     | Fig | 11. Individual |     | stationary |     | purchasing | behavior |     | process |     |     |     |
| --- | --- | --- | -------------- | --- | ---------- | --- | ---------- | -------- | --- | ------- | --- | --- | --- |
To capture individual purchasing behavior, we use a MMC. A MMC [34] models the
mobility behavior of an individual as a discrete stochastic process in which the
probability of moving to a state (i.e., point-of-interest (POI)) depends only on the
previously visited state and the probability distribution of the transitions between
11(a)).
|     |     | states. | In  | our case, | POIs | represent | the | merchants | visited | by  | clients | (see Fig. |     |
| --- | --- | ------- | --- | --------- | ---- | --------- | --- | --------- | ------- | --- | ------- | --------- | --- |
More precisely, a MMC is composed of a set of states M ,M , ,M where N is
|     |     |     |     |     |     |     |     |     |     | { 1 | 2 ··· | N } |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ----- | --- | --- |
the total number of merchants, in which a transaction takes place. Transitions, such as
T(u)
|     |     |       | (t), | represent | the | probability | of  | a user | u moving | from | state | M to state | M   |
| --- | --- | ----- | ---- | --------- | --- | ----------- | --- | ------ | -------- | ---- | ----- | ---------- | --- |
|     |     | Mi,Mj |      |           |     |             |     |        |          |      |       | i          | j   |
during the interval t of 7 days (see Fig. 11(b)). Finally, we computed the steady state
probability vector π(u)(t) where each π(u) (t) represents the probability of purchase of a
i
|     |     | product | in  | merchant | i from | the | user u | during | the t | period | (see Fig. | 11(c)). |     |
| --- | --- | ------- | --- | -------- | ------ | --- | ------ | ------ | ----- | ------ | --------- | ------- | --- |
(cid:88)
|     |     |     |     |     |     |     | Π(u) |     | π(u) |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | ---- | --- | ---- | --- | --- | --- | --- |
|     |     |     |     |     |     |     | (t)= |     | (t)  |     |     |     | (4) |
|     |     |     |     |     |     |     | K    |     | i    |     |     |     |     |
i∈K
|     |     |     |     |     | (cid:110) Π(u) | (cid:12) |     |     |     |     | Π(u) | Π(u) | (cid:111) |
| --- | --- | --- | --- | --- | -------------- | -------- | --- | --- | --- | --- | ---- | ---- | --------- |
Rel(u)(t)= (t)(cid:12) [1,...,13], with (cid:48) > , (t) (t) (5)
|     |     |     |     |     | K   | (cid:12) |     |     |     |     | K   | K(cid:48) |     |
| --- | --- | --- | --- | --- | --- | -------- | --- | --- | --- | --- | --- | --------- | --- |
|     |     |     |     |     |     | K∈       |     |     | ∀K  | K   |     | ≤         |     |
In our context, since we are more interested by the type of goods purchased than by the
specific merchant, we aggregated in (4) the steady state vector Π (t) that represents
K
the probability of completing a purchase in a given COICOP category (e.g., health,
K
or clothing and footwear categories). In (5) we created a relevance metric set Rel(u)(t)
sorted in a descending order (see Fig. 11(d)). Therefore we used the relevance metric to
compute the discounted cumulative gain (DCG) in (6) to measure the consumption
variation over time for individuals. The principle behind this metric is that COICOP
categories with higher probability Π are more relevant. In (7) we capture the
|     |     |     |     | K   |     |     |     | K   |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
purchasing variation between consecutive periods for the same individual u. Finally, in
(8) to capture the purchase variation for all individuals the mean of all individuals’
|        |          | nDGC | is  | computed | for each | period | t.  |     |     |     |     |     |       |
| ------ | -------- | ---- | --- | -------- | -------- | ------ | --- | --- | --- | --- | --- | --- | ----- |
| August | 12, 2020 |      |     |          |          |        |     |     |     |     |     |     | 16/28 |

|     |     |     |     |            | |K|      | 2Rel( u)(t) | 1   |     |     |
| --- | --- | --- | --- | ---------- | -------- | ----------- | --- | --- | --- |
|     |     |     |     | DGC(u)(t)= | (cid:88) | i           |     |     |     |
|     |     |     |     |            |          | −           |     |     | (6) |
log (i+1)
2
i=1
DGC(u)(t)
|     |     |     |     | nDCG(u)(t)= |     |     |     |     | (7) |
| --- | --- | --- | --- | ----------- | --- | --- | --- | --- | --- |
DGC(u)(t
1)
−
|     |     |     |     |          | 1   | (cid:88)   |     |     |     |
| --- | --- | --- | --- | -------- | --- | ---------- | --- | --- | --- |
|     |     |     |     | nDCG(t)= |     | nDGC(u)(t) |     |     |     |
(8)
u
|     |     |             |       |     | | | | u   |     |     |     |
| --- | --- | ----------- | ----- | --- | --- | --- | --- | --- | --- |
|     |     | Transaction | graph |     |     |     |     |     |     |
Based on the transaction dataset, we can define the transaction graph as a list of
G
temporal snapshots =[G t0 ,...,G tk ] where G t (V,E(t),W(t)) is a weighted directed
G
graph in which nodes V represent the merchant. An edge e (t) exists if there is at least
ij
i
one credit or debit card holder that completed a purchase with merchant and then
merchant j during the interval [t 4,t+4] (in days). The weights represent w (t), the
|     |     |     |     |     | −   |     |     |     | ij  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
number of co-transactions made by different credit card holders during the interval
interval [t 4,t+4] between merchant i and merchant j. The orientation of the edge
−
represents the temporal order of the purchase sequence. For instance, given the
|     |     | following | purchase pattern | of  | user l during | the interval [t | 4,t | +4] : |     |
| --- | --- | --------- | ---------------- | --- | ------------- | --------------- | --- | ----- | --- |
0 0
−
P(l) (t 1),P(l) (t +1),P(l) (t +3) , the directed edges, (u,v) and (v,w) would be
|     |     | u 0     | v 0             | w        | 0      |     |     |     |     |
| --- | --- | ------- | --------------- | -------- | ------ | --- | --- | --- | --- |
|     |     | {       | −               |          | }      |     |     |     |     |
|     |     | present | in graph in the | snapshot | G t0 . |     |     |     |     |
PageRank
PageRank quantifies the importance of nodes (centrality) in a network by computing
the dominant eigenvector of the PageRank matrix (or Google matrix [35]). Using the
PageRank algorithm we computed the ranking c i (t) (9) of all merchants i in our dataset
at each given instant t, where W(t) is the weighted adjacency matrix of the snapshot
|     |     | G of transaction | graph | .   |     |     |     |     |     |
| --- | --- | ---------------- | ----- | --- | --- | --- | --- | --- | --- |
t
G
1
|     |     |     |     | C(t)=αS(t)−1W(t)T |     |        | 11T |     |     |
| --- | --- | --- | --- | ----------------- | --- | ------ | --- | --- | --- |
|     |     |     |     |                   |     | +(1 α) |     |     | (9) |
− N
Here s (t)= (cid:80)N w (t) , 1=[1,...,1]T and α=0.85. We derived the evolution of
|     |     | ii  | j=1 | ij  |     |     |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
the ranking of each merchant r i (t) by computing the PageRank of each snapshot
G(t ),...,G(t ) of our dataset. Finally, we computed the normalized ranking
|     |     | 0           | k            |          |         |             |     |     |     |
| --- | --- | ----------- | ------------ | -------- | ------- | ----------- | --- | --- | --- |
|     |     | r (t) [0,1] |              |          | i       | t           |     |     |     |
|     |     | i           | (10) of each | merchant | at time | as follows: |     |     |     |
∈
c i (t) 1
|     |     |     |     |     | r (t)=1 | −         |     |     | (10) |
| --- | --- | --- | --- | --- | ------- | --------- | --- | --- | ---- |
|     |     |     |     |     | i −     | max c (t) |     |     |      |
i i
In Fig. 12, we can observe several examples of the PageRank evolution in time for
distinct merchants.
|     |     | Time       | series clustering |        |                   |         |           |         |     |
| --- | --- | ---------- | ----------------- | ------ | ----------------- | ------- | --------- | ------- | --- |
|     |     | To cluster | the time series   | of the | ranking evolution | of each | merchant, | we used |     |
1d-SAX [36] a method for representing a time series as a sequence of symbols containing
information about the average and trend of the series on a segment. Symbolic aggregate
approximation (SAX) is one of the main symbolization techniques for time series. Our
goal was to cluster the merchant ranking evolution according to the merchants’
behavior, especially during the main ENSO event of Feb. 2017. To do so, we used the
| August | 12, 2020 |     |     |     |     |     |     |     | 17/28 |
| ------ | -------- | --- | --- | --- | --- | --- | --- | --- | ----- |

Fig 12. Example of the normalized rank evolution of merchants in Lima, Peru, during
the interval of January 2017 to April 2017. a) Starbucks coffee shop. b) Fast food
|     |     | restaurant. | c)  | Supermarket. |     | d) Restaurant. |     |     |     |     |     |     |
| --- | --- | ----------- | --- | ------------ | --- | -------------- | --- | --- | --- | --- | --- | --- |
1d-SAX algorithm to help extract the main trends in each time series. The 1d-SAX
|     |     | algorithm | is       | based on   | three main  | steps:        |          |           |        |          |            |     |
| --- | --- | --------- | -------- | ---------- | ----------- | ------------- | -------- | --------- | ------ | -------- | ---------- | --- |
|     |     | 1.        | Divide   | the time   | series      | into segments |          | of length | L.     |          |            |     |
|     |     | 2.        | Compute  | the linear | regression  |               | of the   | time      | series | on each  | segment.   |     |
|     |     | 3.        | Quantize | these      | regressions | into          | a symbol | from      | an     | alphabet | of size N. |     |
After the 1d-SAX transformation (see Fig. 13 for different steps of the transformation of
the time series), we clustered the time series using the standard K-mean algorithm
using the Euclidean distance as the distance metric. In Fig. 14 we depict the silhouette
score of our clustering method across different parameters range of cluster numbers and
segment lengths. Based on sensitivity analysis we determined that six clusters and a
segment length L=15 led to an effective trade-off for clustering our time series with an
|     |     | alphabet | size | of N =8. |     |     |     |     |     |     |     |     |
| --- | --- | -------- | ---- | -------- | --- | --- | --- | --- | --- | --- | --- | --- |
|     |     |          |      |          |     | 4   |     |     |     | 4   |     |     |
|     |     |          |      | a        |     |     | b   |     |     | c   |     |     |
|     |     |          | 100  |          |     | 3   |     |     |     | 3   |     |     |
|     |     |          |      |          |     | 2   |     |     |     | 2   |     |     |
90
|     |     |     |     |     |     | 1   |     |     |     | 1   |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|     |     |     | 80  |     |     | 0   |     |     |     | 0   |     |     |
|     |     |     | 70  |     |     | − 1 |     |     |     | − 1 |     |     |
|     |     |     |     |     |     | 2   |     |     |     | 2   |     |     |
|     |     |     | 60  |     |     | −   |     |     |     | −   |     |     |
|     |     |     |     |     |     | 3   |     |     |     | 3   |     |     |
|     |     |     |     |     |     | −   |     |     |     | −   |     |     |
50
|     |     |     |     |      |       | − 4 |      |     |        | − 4 |              |     |
| --- | --- | --- | --- | ---- | ----- | --- | ---- | --- | ------ | --- | ------------ | --- |
|     |     |     |     | 0 25 | 50 75 | 100 | 0 25 | 50  | 75 100 | 0   | 25 50 75 100 |     |
Fig 13. Example of preprocessing step used to prepare the time series before the
|     |     |     |     |     | tslearn |     |     |     |     |     | r (t) |     |
| --- | --- | --- | --- | --- | ------- | --- | --- | --- | --- | --- | ----- | --- |
clustering step using the tool chain [37]. a) Row time series i of the rank of
merchant i over time. b) The time series r (t) was standardized by subtracting the
i
mean and dividing by the variance. c) The 1d-SAX transformation was applied to the
|        |          | standardized |     | time series | r i (t) | with | an alphabet |     | size of | N =8. |     |       |
| ------ | -------- | ------------ | --- | ----------- | ------- | ---- | ----------- | --- | ------- | ----- | --- | ----- |
| August | 12, 2020 |              |     |             |         |      |             |     |         |       |     | 18/28 |

25
20
15
10
2 4 6 8 10 12
#Cluster
tnemegeS#
0.09
0.08
0.07
0.06
0.05
0.04
erocsetteuohlis
Fig 14. Silhouette score
Tracking the evolution of the core/periphery structure of the
transaction graph
Many networks exhibit a core/periphery structure [38,39], in which a set of nodes forms
a densely connected group that governs the overall behavior of the network. This
structure is recognized as a key mesoscale structure in complex networks that influences
the functionality of a network, as demonstrated in the delivery of information in the
Internet [40].
To partition nodes into two classes, core V and periphery V , we used the method
c p
developed by Ma et al. [28]. The proposed method ranks the nodes by degree in
descending order. For a given node, it divides its links into two groups: those with
nodes of a higher rank and those of a lower rank. More formally, a node of rank r has
degree k the number of links it shares with nodes of a higher rank is k+, and the
r r
number of links with nodes of a lower rank is k k+. To distinguish the core’s node
r − r
from the remaining nodes, we examined the nodes starting from the node of the highest
rank toward the node of the lowest rank and stopped when we identified node r∗ where
k+ reached its maximum as depicted in Fig. 15. Because the definition of a rich core
r
can be extended to weighted directed networks, we used the method proposed in [28] to
extract the core/periphery structure of all graph snapshots G (weighted and directed)
t
of the full transaction graph (V,E). Finally, we computed the size of the core V (t)
c
G | |
over time where V (t) V.
c
⊆
Acknowledgments
This work was conducted at the Energy4Climate Interdisciplinary Center (E4C) of IP
Paris and Ecole des Ponts ParisTech. It was supported by 3rd Programme
d’Investissements d’Avenir ANR-18-EUR-0006. It was also supported by the STIC
AM-SUD program through the 04-2017 PEDESTAL project. The authors thank the
computing resource platform of Telecom SudParis and M. Christian Bac for his help.
The authors thank M. Latapy for many useful discussions.
Author Contributions
Computing Resources: VG Data Curation: HAS, VG, MNP Developed the
Methods: HAS, VG, MNP Design the experiment: HAS, VG, MNP, MB
August 12, 2020 19/28

105
|     |     |     |     |     |     |     | nodes in the core |     | node at the periphery  |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | ----------------- | --- | ---------------------- | --- | --- | --- |
104
sedonrehgihotthgiew
103
102
101
|     |     |     |     |     |     | 10 0 00 |     | 101 | 102 | 103 | 104 |     |
| --- | --- | --- | --- | --- | --- | ------- | --- | --- | --- | --- | --- | --- |
1
Rank
Fig 15. Example of core/periphery detection for the weighted directed network. Here
the core/periphery of a slice of the transaction graph of May 2, 2017 is displayed. The
|     |     | core | size | is V | (t)=82 |     | for a graph |     | with V =11,179 | vertices |     |     |
| --- | --- | ---- | ---- | ---- | ------ | --- | ----------- | --- | -------------- | -------- | --- | --- |
core
|     |     |                |     | |   |      | |   |       |     | | |    |          |         |     |
| --- | --- | -------------- | --- | --- | ---- | --- | ----- | --- | ------ | -------- | ------- | --- |
|     |     | Investigation: |     |     | HAS, | MNP | Wrote | the | paper: | HAS, VG, | MNP, MB |     |
Data availability
The dataset used for experiments was obtained from a Peruvian private financial entity
(BBVA), the dataset was provided to us in the context of a long-standing collaboration
between the Universidad del Pac´ıfico (especially the BITMAP team) and the BBVA
|     |     | through |     | a specific | multidisciplinary |     |     | research | agreement. |     |     |     |
| --- | --- | ------- | --- | ---------- | ----------------- | --- | --- | -------- | ---------- | --- | --- | --- |
Although the dataset provided to us was anonymized and did not contain any
personal or identity information about the bank’s customers. The dataset provided
contains enough information such that the anonymized ID could be subject to data
reunification [41]. In that sense, sharing the raw version of this dataset can potentially
breach the privacy of bank’s customers. For all these reasons, we are unable to share
|     |     | the | raw | dataset | version | of  | the dataset |     | we have been | working | with. |     |
| --- | --- | --- | --- | ------- | ------- | --- | ----------- | --- | ------------ | ------- | ----- | --- |
Even if we are unable to share the original dataset, we are pleased to share datasets
derived from the used dataset but that won’t compromise the privacy of the BBVA
customers. Moreover it would enable the reviewer to reproduce our study and be of help
for anybody who aims to understand the consumption behavior at the country level.
|     |     |     | The | dataset | we provide |     | contains | the | following | data: |     |     |
| --- | --- | --- | --- | ------- | ---------- | --- | -------- | --- | --------- | ----- | --- | --- |
•
The consumption data aggregated by districts to enable replication of our study
•
|     |     |     | The | transaction |     | graphs | datasets |     | we used in | this paper. |     |     |
| --- | --- | --- | --- | ----------- | --- | ------ | -------- | --- | ---------- | ----------- | --- | --- |
All the data are available at https://doi.org/10.7910/DVN/LYXBGR. Please note
that the dataset we provide will be shared under the Common Creative CC-BY v.4.0
license.
References
1. Peru: Rainy season - Situation Report No. 12 (as of 27 June 2017) - Peru —
|     |     |     | ReliefWeb; |     | 2017. | Available |     | from: | https://reliefweb.int/report/peru/ |     |     |     |
| --- | --- | --- | ---------- | --- | ----- | --------- | --- | ----- | ---------------------------------- | --- | --- | --- |
peru-rainy-season-situation-report-no-12-27-june-2017.
|        |          |     | 2. Hallegatte |     | S,                                       | Hourcade | JC,      | Dumas | P. Why       | economic | dynamics matter            | in    |
| ------ | -------- | --- | ------------- | --- | ---------------------------------------- | -------- | -------- | ----- | ------------ | -------- | -------------------------- | ----- |
|        |          |     | assessing     |     | climate                                  | change   | damages: |       | Illustration | on       | extreme events. Ecological |       |
|        |          |     | Economics.    |     | 2007;doi:10.1016/j.ecolecon.2006.06.006. |          |          |       |              |          |                            |       |
| August | 12, 2020 |     |               |     |                                          |          |          |       |              |          |                            | 20/28 |

3. Ahmed SA, Diffenbaugh NS, Hertel TW. Climate volatility deepens poverty
|     |     | vulnerability |     | in developing |     | countries. |     | Environmental |     | Research Letters. |     |     |
| --- | --- | ------------- | --- | ------------- | --- | ---------- | --- | ------------- | --- | ----------------- | --- | --- |
2009;doi:10.1088/1748-9326/4/3/034004.
4. for Primary Industries M. ERCC PORTAL Emergency Response Coordination
Centre (ERCC) European Civil Protection and Humanitarian Aid Operations;
|     |     | 2017. | https://erccportal.jrc.ec.europa.eu/Preparedness/ |     |     |     |     |     |     |     |     |     |
| --- | --- | ----- | ------------------------------------------------- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
Country-profiles/country/Peru/iso3/PER.
5. Carleton TA, Hsiang SM. Social and economic impacts of climate. Science.
|     |     | 2016;353(6304). |     | doi:10.1126/science.aad9837. |     |     |     |     |     |     |     |     |
| --- | --- | --------------- | --- | ---------------------------- | --- | --- | --- | --- | --- | --- | --- | --- |
6. Adger WN, Hughes TP, Folke C, Carpenter SR, Rockstr¨om J. Social-ecological
resilience to coastal disasters. Science (New York, NY). 2005;309(5737):1036–9.
doi:10.1126/science.1112122.
7. Strengthening Post-Hurricane Supply Chain Resilience. National Academies
|     |     | Press; | 2020. | Available |     | from: | https://www.nap.edu/catalog/25490. |     |     |     |     |     |
| --- | --- | ------ | ----- | --------- | --- | ----- | ---------------------------------- | --- | --- | --- | --- | --- |
8. Wang Q, Taylor JE. Quantifying Human Mobility Perturbation and Resilience in
|     |     | Hurricane |     | Sandy. | PLoS | ONE. | 2014;9(11):e112608. |     |     |     |     |     |
| --- | --- | --------- | --- | ------ | ---- | ---- | ------------------- | --- | --- | --- | --- | --- |
doi:10.1371/journal.pone.0112608.
9. Martinez EA, Rubio MH, Martinez RM, Arias JM, Patane D, Zerbe A, et al.
|     |     | Measuring   |     | Economic | Resilience |          | to Natural |      | Disasters | with Big Economic |       |     |
| --- | --- | ----------- | --- | -------- | ---------- | -------- | ---------- | ---- | --------- | ----------------- | ----- | --- |
|     |     | Transaction |     | Data.    | In:        | the Data | For        | Good | Exchange; | 2016.Available    | from: |     |
http://arxiv.org/abs/1609.09340.
10. Guan X, Chen C, Work D. Tracking the Evolution of Infrastructure Systems and
Mass Responses Using Publically Available Data. PLOS ONE. 2016;11(12):1–17.
doi:10.1371/journal.pone.0167267.
11. Niles MT, Emery BF, Reagan AJ, Dodds PS, Danforth CM. Social media usage
|     |     | patterns |     | during natural |     | hazards. | PLOS | ONE. | 2019;14(2):1–16. |     |     |     |
| --- | --- | -------- | --- | -------------- | --- | -------- | ---- | ---- | ---------------- | --- | --- | --- |
doi:10.1371/journal.pone.0210484.
12. Kuˇsen E, Strembeck M. An analysis of emotion-exchange motifs in multiplex
|     |     | networks |     | during emergency |     | events. | Applied |     | Network | Science. 2019;4(1):8. |     |     |
| --- | --- | -------- | --- | ---------------- | --- | ------- | ------- | --- | ------- | --------------------- | --- | --- |
doi:10.1007/s41109-019-0115-6.
13. Bagrow JP, Wang D, Baraba´si AL. Collective response of human populations to
large-scale emergencies. PLoS ONE. 2011;6(3). doi:10.1371/journal.pone.0017680.
14. Eyre R, De Luca F, Simini F. Social media usage reveals recovery of small
businesses after natural hazard events. Nature Communications. 2020;11(1):1629.
doi:10.1038/s41467-020-15405-7.
15. Di Clemente R, Luengo-Oroz M, Travizano M, Xu S, Vaitla B, Gonz´alez MC.
Sequences of purchases in credit card data reveal lifestyles in urban populations.
|     |     | Nature | Communications. |     |     | 2018;9(1):3330. |     | doi:10.1038/s41467-018-05690-8. |     |     |     |     |
| --- | --- | ------ | --------------- | --- | --- | --------------- | --- | ------------------------------- | --- | --- | --- | --- |
16. Leo Y, Fleury E, Alvarez-Hamelin JI, Sarraute C, Karsai M. Socioeconomic
correlations and stratification in social-communication networks. Journal of The
|     |     | Royal   | Society   | Interface. |          | 2016;13(125):20160598. |        |                 |     | doi:10.1098/rsif.2016.0598. |     |     |
| --- | --- | ------- | --------- | ---------- | -------- | ---------------------- | ------ | --------------- | --- | --------------------------- | --- | --- |
|     |     | 17. Leo | Y, Karsai | M,         | Sarraute | C,                     | Fleury | E. Correlations |     | and dynamics                | of  |     |
consumption patterns in social-economic networks. Social Network Analysis and
|        |          | Mining. | 2018;8(1):9. |     | doi:10.1007/s13278-018-0486-1. |     |     |     |     |     |     |       |
| ------ | -------- | ------- | ------------ | --- | ------------------------------ | --- | --- | --- | --- | --- | --- | ----- |
| August | 12, 2020 |         |              |     |                                |     |     |     |     |     |     | 21/28 |

18. Guidotti R, Gabrielli L, Monreale A, Pedreschi D, Giannotti F. Discovering
temporal regularities in retail customers’ shopping behavior. EPJ Data Science.
|     |     | 2018;7(1):6. | doi:10.1140/epjds/s13688-018-0133-0. |     |     |     |     |     |     |     |     |
| --- | --- | ------------ | ------------------------------------ | --- | --- | --- | --- | --- | --- | --- | --- |
19. Nevill-Manning CG, Witten IH. Identifying Hierarchical Structure in Sequences:
|     |     | A Linear-time     |     | Algorithm. | J Artif        | Int | Res.  | 1997;7(1):67–82. |             |     |     |
| --- | --- | ----------------- | --- | ---------- | -------------- | --- | ----- | ---------------- | ----------- | --- | --- |
|     |     | 20. VISA Merchant |     | Category   | Classification |     | (MCC) | codes            | directory;. |     |     |
https://www.dm.usda.gov/procurement/card/card_x/mcc.pdf.
21. Youn H, Bettencourt LMA, Lobo J, Strumsky D, Samaniego H, West GB.
Scaling and universality in urban economic diversification. Journal of The Royal
|     |     | Society | Interface. | 2016;13(114):20150937. |     |     |     | doi:10.1098/rsif.2015.0937. |     |     |     |
| --- | --- | ------- | ---------- | ---------------------- | --- | --- | --- | --------------------------- | --- | --- | --- |
22. Sobolevsky S, Sitko I, Tachet des Combes R, Hawelka B, Murillo Arias J, Ratti C.
|     |     | Cities through   |     | the Prism                         | of Peoples |     | Spending | Behavior. | PLOS | ONE. |     |
| --- | --- | ---------------- | --- | --------------------------------- | ---------- | --- | -------- | --------- | ---- | ---- | --- |
|     |     | 2016;11(2):1–19. |     | doi:10.1371/journal.pone.0146291. |            |     |          |           |      |      |     |
23. Brodersen KH, Gallusser F, Koehler J, Remy N, Scott SL, et al. Inferring causal
|     |     | impact using | Bayesian           |     | structural | time-series |     | models. | The Annals | of Applied |     |
| --- | --- | ------------ | ------------------ | --- | ---------- | ----------- | --- | ------- | ---------- | ---------- | --- |
|     |     | Statistics.  | 2015;9(1):247–274. |     |            |             |     |         |            |            |     |
24. Torres D, Ortiz F, Solis T, Tapia W, Merino G, Pintado J, et al. Manual de
PERU´.
Evaluaci´on de dan˜os y An´alisis de Necesidades EDAN Sinco Industria
|     |     | Gr´afica | EIRL; | 2018. |     |     |     |     |     |     |     |
| --- | --- | -------- | ----- | ----- | --- | --- | --- | --- | --- | --- | --- |
25. Pennacchioli D, Coscia M, Rinzivillo S, Giannotti F, Pedreschi D. The retail
|     |     | market as | a complex | system. |     | EPJ Data | Science. |     | 2014;3(1):33. |     |     |
| --- | --- | --------- | --------- | ------- | --- | -------- | -------- | --- | ------------- | --- | --- |
doi:10.1140/epjds/s13688-014-0033-x.
26. Peixoto TP, Bornholdt S. Evolution of Robust Network Topologies: Emergence of
|     |     | Central | Backbones. | Physical |     | Review | Letters. | 2012;109(11):118703. |     |     |     |
| --- | --- | ------- | ---------- | -------- | --- | ------ | -------- | -------------------- | --- | --- | --- |
doi:10.1103/PhysRevLett.109.118703.
27. Verma T, Russmann F, Arau´jo NAM, Nagler J, Herrmann HJ. Emergence of
|     |     | core–peripheries |     | in networks. |     | Nature | Communications. |     | 2016;7(1):10441. |     |     |
| --- | --- | ---------------- | --- | ------------ | --- | ------ | --------------- | --- | ---------------- | --- | --- |
doi:10.1038/ncomms10441.
|     |     | 28. Ma A, Mondrag´on |     | RJ.                               | Rich-Cores | in  | Networks. | PLOS | ONE. |     |     |
| --- | --- | -------------------- | --- | --------------------------------- | ---------- | --- | --------- | ---- | ---- | --- | --- |
|     |     | 2015;10(3):e0119678. |     | doi:10.1371/journal.pone.0119678. |            |     |           |      |      |     |     |
29. Gambs S, Killijian MO, del Prado Cortez MN. De-anonymization attack on
|     |     | geolocated | data. | Journal | of Computer |     | and | System | Sciences. |     |     |
| --- | --- | ---------- | ----- | ------- | ----------- | --- | --- | ------ | --------- | --- | --- |
2014;80(8):1597–1614.
30. Nunez-del Prado M, Nin J. Revisiting online anonymization algorithms to ensure
location privacy. Journal of Ambient Intelligence and Humanized Computing.
|     |     | 2019; p. | 1–12. |     |     |     |     |     |     |     |     |
| --- | --- | -------- | ----- | --- | --- | --- | --- | --- | --- | --- | --- |
31. Xu C, Ren J, Zhang D, Zhang Y, Qin Z, Ren K. GANobfuscator: Mitigating
information leakage under GAN via differential privacy. IEEE Transactions on
|     |     | Information | Forensics |     | and Security. |     | 2019;14(9):2358–2371. |     |     |     |     |
| --- | --- | ----------- | --------- | --- | ------------- | --- | --------------------- | --- | --- | --- | --- |
32. Schanzenbach DW, Nunn R, Bauer L, Mumford M. Where does all the money go:
Shifts in household spending over the past 30 years. Brookings Institution, The
|        |          | Hamilton | Project. | 2016;. |     |     |     |     |     |     |       |
| ------ | -------- | -------- | -------- | ------ | --- | --- | --- | --- | --- | --- | ----- |
| August | 12, 2020 |          |          |        |     |     |     |     |     |     | 22/28 |

|     |     | 33. Classification | of Individual |     | Consumption |     | According | to  | Purpose;. |     |
| --- | --- | ------------------ | ------------- | --- | ----------- | --- | --------- | --- | --------- | --- |
https://en.wikipedia.org/wiki/Classification_of_Individual_
Consumption_by_Purpose.
34. Gambs S, Killijian MO, del Prado Cortez MNn. Show Me How You Move and I
|     |     | Will Tell | You Who | You Are. | In: Proceedings |     | of  | the 3rd | ACM SIGSPATIAL |     |
| --- | --- | --------- | ------- | -------- | --------------- | --- | --- | ------- | -------------- | --- |
International Workshop on Security and Privacy in GIS and LBS. SPRINGL ’10;
|     |     | 2010. p. | 34–41. |     |     |     |     |     |     |     |
| --- | --- | -------- | ------ | --- | --- | --- | --- | --- | --- | --- |
35. Langville AN, Meyer CD. Google’s PageRank and beyond : the science of search
|     |     | engine | rankings. Princeton |     | University | Press; | 2012. |     |     |     |
| --- | --- | ------ | ------------------- | --- | ---------- | ------ | ----- | --- | --- | --- |
36. Malinowski S, Guyet T, Quiniou R, Tavenard R. 1d-SAX: A Novel Symbolic
|     |     | Representation | for | Time | Series. In: | Tucker | A, H¨oppner |     | F, Siebes A, | Swift S, |
| --- | --- | -------------- | --- | ---- | ----------- | ------ | ----------- | --- | ------------ | -------- |
editors. Advances in Intelligent Data Analysis XII. Springer Berlin Heidelberg;
|     |     | 2013. p. | 273–284. |     |     |     |     |     |     |     |
| --- | --- | -------- | -------- | --- | --- | --- | --- | --- | --- | --- |
37. Tavenard R, Faouzi J, Vandewiele G. tslearn: A machine learning toolkit
|     |     | dedicated | to time-series | data; | 2017. |     |     |     |     |     |
| --- | --- | --------- | -------------- | ----- | ----- | --- | --- | --- | --- | --- |
38. Borgatti SP, Everett MG. Models of core/periphery structures. Social Networks.
|     |     | 2000;21(4):375–395. |     | doi:10.1016/S0378-8733(99)00019-2. |     |     |     |     |     |     |
| --- | --- | ------------------- | --- | ---------------------------------- | --- | --- | --- | --- | --- | --- |
39. Holme P. Core-periphery organization of complex networks. Physical Review E -
|     |     | Statistical, | Nonlinear, | and | Soft Matter | Physics. |     | 2005;72(4). |     |     |
| --- | --- | ------------ | ---------- | --- | ----------- | -------- | --- | ----------- | --- | --- |
doi:10.1103/PhysRevE.72.046111.
40. Carmi S, Havlin S, Kirkpatrick S, Shavitt Y, Shir E. A model of Internet
topology using k-shell decomposition. Proceedings of the National Academy of
|     |     | Sciences | of the United | States | of America. |     | 2007;104(27):11150–11154. |     |     |     |
| --- | --- | -------- | ------------- | ------ | ----------- | --- | ------------------------- | --- | --- | --- |
doi:10.1073/pnas.0701175104.
41. De Montjoye YA, Hidalgo CA, Verleysen M, Blondel VD. Unique in the crowd:
|     |     | The privacy | bounds | of human | mobility. | Scientific |     | reports. | 2013;3:1376. |     |
| --- | --- | ----------- | ------ | -------- | --------- | ---------- | --- | -------- | ------------ | --- |
42. Censos Nacionales 2017: XII de Poblacio´n, VII de Vivienda y III de Comunidades
|     |     | Ind´ıgenas;. | https://www.inei.gob.pe/media/MenuRecursivo/ |     |     |     |     |     |     |     |
| --- | --- | ------------ | -------------------------------------------- | --- | --- | --- | --- | --- | --- | --- |
publicaciones_digitales/Est/Lib1544/.
|     |     | 43. Computop‘s | Payment | & e-Commerce |     | Report | Latin | America; | 2017. |     |
| --- | --- | -------------- | ------- | ------------ | --- | ------ | ----- | -------- | ----- | --- |
https://www.computop.com/fileadmin/user_upload/Downloads_Content/
deutsch/CountryReports/CountryGuide_Latin_America.pdf.
44. Leo Y, Karsai M, Sarraute C, Fleury E. Correlations of consumption patterns in
|     |     | social-economic | networks. |     | In: 2016 | IEEE/ACM |     | International | Conference | on  |
| --- | --- | --------------- | --------- | --- | -------- | -------- | --- | ------------- | ---------- | --- |
Advances in Social Networks Analysis and Mining (ASONAM). IEEE; 2016. p.
493–500.
|     |     | 45. Population | Pyramids | of Peru | in 2019;. |     |     |     |     |     |
| --- | --- | -------------- | -------- | ------- | --------- | --- | --- | --- | --- | --- |
https://www.populationpyramid.net/peru/2019/.
|     |     | 46. GINI Peru;. |     |     |     |     |     |     |     |     |
| --- | --- | --------------- | --- | --- | --- | --- | --- | --- | --- | --- |
https://data.worldbank.org/indicator/SI.POV.GINI?locations=PE.
47. Yamada G, Castro JF, Oviedo N, et al. Revisitando el coeficiente de Gini en el
|        |          | Peru´: el | rol de las | pol´ıticas | pu´blicas | en la | evoluci´on | de  | la desigualdad; | 2016. |
| ------ | -------- | --------- | ---------- | ---------- | --------- | ----- | ---------- | --- | --------------- | ----- |
| August | 12, 2020 |           |            |            |           |       |            |     |                 | 23/28 |

48. Yamada G, Castro JF, Bacigalupo J, et al. Desigualdad monetaria en un
contexto de r´apido crecimiento econ´omico: El caso reciente del Peru´. Revista
|     |     | Estudios Econ´omicos. | 2012;24:65–77. |     |     |     |
| --- | --- | --------------------- | -------------- | --- | --- | --- |
NIN˜O
49. Informe T´ecnico Extraordinario 001-2017/ENFENEL COSTERO 2017;
2017. http://www.imarpe.pe/imarpe/archivos/informes/imarpe_inftco_
informe__tecnico_extraordinario_001_2017.pdf.
50. Batagelj V, Zaverˇsnik M. Fast algorithms for determining (generalized) core
|        |          | groups in social   | networks. Advances             | in Data Analysis | and Classification. |       |
| ------ | -------- | ------------------ | ------------------------------ | ---------------- | ------------------- | ----- |
|        |          | 2011;5(2):129–145. | doi:10.1007/s11634-010-0079-y. |                  |                     |       |
| August | 12, 2020 |                    |                                |                  |                     | 24/28 |

|     |     | Supporting   | Information |     |           |      |                |     |
| --- | --- | ------------ | ----------- | --- | --------- | ---- | -------------- | --- |
|     |     | Demographics | information |     | and known | bias | in our dataset |     |
As of July 2019, the Peruvian National Institute of Statistics and Informatics reported a
population of approximately 33 million, of which 22 million represent an economically
active population [42]. In the capital city, Lima there are 8.5 million inhabitants. As a
reference, the Peruvian economy is one of the world’s fastest-growing economies as of
2000. Like the rest of Latin America, Peru has a fast-growing debit/credit card market,
and 39% of the population owns a bank account, while 29% of the population owns a
credit/debit card [43]. We estimated individuals’ socio-economic class in our dataset by
relying on the consumption captured by the average monthly purchase (AMP) P [44]
i
(11).
|     |     |     |     |     | (cid:80) | P (t) |     |      |
| --- | --- | --- | --- | --- | -------- | ----- | --- | ---- |
|     |     |     |     |     | t∈T      | i     |     |      |
|     |     |     |     |     | P =      |       |     | (11) |
i T
i
|     |     |     |     |     | | | |     |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
Here P (t) is the total number of purchases by individual i in a given month t, and
i
T is the number of months in which individual i made at least one purchase. It
| | i
should be noted that we considered only individuals with more than $30 of purchases in
all months. We then computed the normalized cumulative distribution function C(f) as
|     |     | a function | of the fraction | f of people | (12).      |          |     |      |
| --- | --- | ---------- | --------------- | ----------- | ---------- | -------- | --- | ---- |
|     |     |            |                 |             | 1          | (cid:88) |     |      |
|     |     |            |                 |             | C(f)=      | P        |     | (12) |
|     |     |            |                 |             | (cid:80) P | i.       |     |      |
i
|     |     |     |     |     | i   | f   |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
Based on the cumulative AMP, we split the population into nine economic classes
(see Fig. S1 a). Subsequently, we derived a set of demographics from the individuals in
our dataset S1 such as the social class distribution, population pyramid, and gender
imbalance. The population pyramid of our dataset appeared to be in accordance with
the population pyramid of the Peruvian population [45]. However, our dataset appeared
to have a bias toward the male population because we observed a gender imbalance.
This was also observed in a study by [16] that used the same type of dataset for Mexico
|     |     | instead of | Peru. |     |     |     |     |     |
| --- | --- | ---------- | ----- | --- | --- | --- | --- | --- |
Finally, we computed the GINI coefficient G (13) based on the (AMP) and found
coefficient values ranging from G = 0.60 to 0.66 instead of G=0.433, as provided by
the World Bank [46]. This substantial difference between the two coefficients may be
due to two phenomena. First, we may have had an overrepresentation of upper-class
individuals in our dataset that may have biased some of our results [47]. Second, the
GINI coefficient we computed here is based on the AMP only; that is, it is based on
people’s spending instead of taking into account their income plus the benefit received
|     |     | from social | programs | [48]. |     |     |     |     |
| --- | --- | ----------- | -------- | ----- | --- | --- | --- | --- |
(cid:80)n
|     |     |          |                |     | (2i                  | n 1)P i |            |      |
| --- | --- | -------- | -------------- | --- | -------------------- | ------- | ---------- | ---- |
|     |     |          |                | G=  | i=1 (cid:80)−        | −       |            | (13) |
|     |     |          |                |     | n n                  | P       |            |      |
|     |     |          |                |     | i=1                  | i       |            |      |
|     |     | District | level analysis | of  | the Kullback-Leibler |         | divergence |      |
In Fig. S2, we present the daily evolution of the KLD per district of the greater area of
Lima (Peru) over the two years of our dataset. This figure illustrates that the KLD
remained neutral (at approximately zero), which signifies that the spending distribution
of the area remained consistent with the average spending behavior of the district. In
contrast, when a divergence appears, it signifies that the spending distribution shifted
from its normal behavior. Fig. 4 also demonstrates that the February 2017 events
impacted most of Lima’s districts, and a spike on February 20 can be clearly observed.
| August | 12, 2020 |     |     |     |     |     |     | 25/28 |
| ------ | -------- | --- | --- | --- | --- | --- | --- | ----- |

Fig S1. Demographic characteristics of dataset. a) Social class distribution. b)
Average AMP P in each social class and the number of people in each social class. c)
(cid:104) (cid:105)
Age pyramid for males and females. d) Average age in each social class. e) Fraction of
females in each social class.
A subset of districts was also impacted twice by the February and March events,
including the district of Los Olivos, Magdalena del Mar, and San Miguel. The February
event observed was partially due to flooding caused by the Rimac and Huaycoloro rivers
affecting the district of San Juan de Lurigancho. Second, during the March event, there
was a substantial increase in consumption due to low supply and the overvaluation of
necessities, such as mineral water, rice, and meats. Among the 42 districts of Lima,
official reports [49] established that the most affected districts were the districts of
Chaclacayo, San Juan de Lurigancho, Cieneguilla, Punta Hermosa, Pucusana andRimac
(see Fig. S2). In Fig. S2, the KLD measure displays a spike of activity in the reported
districts during the events. This spike is a clear indication that a sudden shift in the
consumption pattern occurred during the events. However, at the macroscopic level, the
change in consumption behavior did not seem to persist for a long time after the events.
Causality analysis of ENSO on individual purchasing behavior
Fig. S3 displays the causal impact of El Nin˜o on the 42 districts of Lima metropolitan
area during March 2017. As in the experiment depicted in Fig. 5, we used the Callao
series as the control. The negatively impacted districts were as follows Pucusana,
Carabayllo, Lurigancho, Los Olivos, Ancon, Chorrillos, Santa Rosa, San Bartolo, La
Molina, Jesus Maria Surquillo, Chaclacayo, Santa Maria del Mar, Villa el Salvador,
Punta Hermosa, Lince and Lurin. In contrast, some districts such as Lima,
Pachacamac, San Isidro, San Borja, El Agustino, Independencia, San Juan Miraflores,
and Miraflores experienced a positive impact. Finally, the remaining districts
experienced a neutral impact.
With regard to the variation in the impact of El Nin˜o between February and March
2017 (see Fig. 5), there was a decrease in the number of negatively impacted districts
from 20 in February to 17 in March (see Fig. S3 a). The same pattern occurred with
August 12, 2020 26/28

|     |     |     | Sanisidro |     | Losolivos |     | Lima |     | Sanluis |     | Ancon |     | Cieneguilla |
| --- | --- | --- | --------- | --- | --------- | --- | ---- | --- | ------- | --- | ----- | --- | ----------- |
1.40
3
2
1
0
4 Sanborja Santaanita Sanmartindeporres Magdalenadelmar Sanmiguel Elagustino
3
0.28
1
0
|     |     |     | Villamariadeltriu |     | Comas |     | Independencia |     | Chorrillos |     | Sanjuandemiraflor |     | Santarosa |
| --- | --- | --- | ----------------- | --- | ----- | --- | ------------- | --- | ---------- | --- | ----------------- | --- | --------- |
4
3
2
1
0.06
|     |     |     | Sanbartolo |     | Lamolina |     | Rimac |     | Jesusmaria |     | Surquillo |     | Ate |
| --- | --- | --- | ---------- | --- | -------- | --- | ----- | --- | ---------- | --- | --------- | --- | --- |
4
3
)1(
D 2
1
0
|     |     |     | Barranco |     | Sanjuandeluriganc |     | Puentepiedra |     | Chaclacayo |     | Santiagodesurco |     | Pueblolibre |
| --- | --- | --- | -------- | --- | ----------------- | --- | ------------ | --- | ---------- | --- | --------------- | --- | ----------- |
0.44
3
2
1
0
|     |     |     | Miraflores |     | Santamariadelmar |     | Villaelsalvador |     | Puntahermosa |     | Lince |     | Lurin |
| --- | --- | --- | ---------- | --- | ---------------- | --- | --------------- | --- | ------------ | --- | ----- | --- | ----- |
4
3
0.22
1
0
|     |     |     | Pucusana |     | Lavictoria |     | Pachacamac |     | Carabayllo |     | Lurigancho |     | Brena |
| --- | --- | --- | -------- | --- | ---------- | --- | ---------- | --- | ---------- | --- | ---------- | --- | ----- |
4
3
2
1
0.00
0.J0ul Oct Jan Apr Jul Oct Jul0O.2ct Jan Apr Jul Oct Jul Oct0J.a4n Apr Jul Oct Jul Oct Jan A0p.6r Jul Oct Jul Oct Jan Apr J0u.l8Oct Jul Oct Jan Apr Jul Oc1t.0
|     |     |     | 2017    |     | 2017    |           | 2017     |     | 2017 |     | 2017 |     | 2017 |
| --- | --- | --- | ------- | --- | ------- | --------- | -------- | --- | ---- | --- | ---- | --- | ---- |
|     |     | Fig | S2. KLD | of  | various | districts | of Lima. |     |      |     |      |     |      |
positively impacted districts with a reduction from 11 in February to 8 in March (see
Fig. S3 b). Finally, we note that more districts became neutral from: 12 in February
|     |     | and    | 18 in March   | (see | Fig. | S3 c).  |     |     |                 |     |       |     |     |
| --- | --- | ------ | ------------- | ---- | ---- | ------- | --- | --- | --------------- | --- | ----- | --- | --- |
|     |     | k-core | decomposition |      |      | dynamic |     | of  | the transaction |     | graph |     |     |
In Fig. S4 we consider the k-core decomposition [50] of the transaction graph to explore
the graph evolution, and how many transactions are distributed in each of the k-shells
of the transaction graph. In Fig. S4 a we considered each time slice of the transaction
graph G at time t and compared it with the shell number of a node u at t+∆t (where
t
∆t=1
|     |     |     | day). | The | fact that | the | figure | is not | symmetric | is an | indication | that | when a |
| --- | --- | --- | ----- | --- | --------- | --- | ------ | ------ | --------- | ----- | ---------- | ---- | ------ |
node steps down from its k-shell position, it goes down many steps, on the contrary
whenever a node enhances its k-shell position, it climbs up only one step at a time. In
Fig. S4 b, we see how the number of transactions is distributed into each of the k-shells
|        |          | (the | sum of | the in-weights |     | of all | nodes | that | belong | to the k-shell | k). |     |       |
| ------ | -------- | ---- | ------ | -------------- | --- | ------ | ----- | ---- | ------ | -------------- | --- | --- | ----- |
| August | 12, 2020 |      |        |                |     |        |       |      |        |                |     |     | 27/28 |

a
|     |     |     | 0   |     | d   |     |     |
| --- | --- | --- | --- | --- | --- | --- | --- |
−10
−20
Pucusana SantaRosa SantaMariadelMar
Carabayllo SanBartolo VillaelSalvador
Lurigancho LosOlivos LaMolina JesusMaria PuntaHermosa Lince
Ancon Surquillo Lurin
|     |     |     | b Chorrillos | Chaclacayo |     |     |     |
| --- | --- | --- | ------------ | ---------- | --- | --- | --- |
8
6
4
2
0
Lima SanBorja SanJuanMirafor
Pachacamac SanIsidro ElAgustino Independencia Mirafores
c
2
0
−2
|     |     |     | 01/02/2017 01/03/2017   | 01/04/2017 01/05/2017      | 01/06/2017                  |     |     |
| --- | --- | --- | ----------------------- | -------------------------- | --------------------------- | --- | --- |
|     |     |     | Cieneguilla             | SanLuis                    | Barranco                    |     |     |
|     |     |     | SanMartindePorres Comas | SantaAnita Magdalenadelmar | SantiagodeSurco PuebloLibre |     |     |
|     |     |     | Ate                     | SanMiguel                  | Lavictoria                  |     |     |
|     |     |     | SanJuandeLurigancho     | VillaMaria                 | Brena                       |     |     |
|     |     |     | PuentePiedra            | Rimac                      | PuntaNegra                  |     |     |
Fig S3. Causal impact at the district level for March 2017. a) List of districts with a
negative impact. b) List of districts with a positive impact. c) List of districts with a
neutral impact. d) Map of Lima showing the districts with a negative (red), positive
|     |     | (green) | and neutral (yellow) | impact. |     |     |     |
| --- | --- | ------- | -------------------- | ------- | --- | --- | --- |
|     |     |         | a                    |         | b   |     |     |
105
20/02
22/02
24/03
snoitcasnart# 104 26/03
103
102
|     |     |     |     |     | 0 5 | 10 15 20 | 25 30 |
| --- | --- | --- | --- | --- | --- | -------- | ----- |
Kshell
Fig S4. The Cores decomposition dynamic of the transaction graph. a) Evolution of
the k-shell overtime. b) Distribution of the number of transaction as function of its
k-shell.
| August | 12, 2020 |     |     |     |     |     | 28/28 |
| ------ | -------- | --- | --- | --- | --- | --- | ----- |