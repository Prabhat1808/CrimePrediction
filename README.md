# CrimePrediction
Addressing the problem of predicting crime occurrence based on historic records
Following research paper was chosen as the starting point: http://urban-computing.com/pdf/CIKM2018deepcrime.pdf [1]

Note: in trainingmodels.py, there are two model architectures defined:
```
1) bi-LSTM
2) RNN
```
Uncomment one of these and keep whichever one you want to use for training.
_____________________________________________________________________________________________
Following data is taken from the NYC OpenData website: https://opendata.cityofnewyork.us/data/
```
1) Crime Records: https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Historic/qgea-i56i
2) 311 complaint records: https://data.cityofnewyork.us/Social-Services/311-Service-Requests-for-2006/hy4q-igkk
3) Points-of-Interest: https://data.cityofnewyork.us/City-Government/Points-Of-Interest/rxuy-2muj
4) Precincts geographical distribution: https://data.cityofnewyork.us/Public-Safety/Police-Precincts/78dh-3ptz
```
We trained our model on the data for year 2006, since at the time of starting this project we couldn't get access to 311 complaint records for after this period. Keep checking for latest data.
Along with the datasets, the above links also contain information describing the data representation and categorization. This might be helful for preprocessing and extracting the relevant information.
_______________________________________________________________________________________________
[1] Chao Huang, Junbo Zhang, Yu Zheng, and Nitesh V. Chawla. 2018. DeepCrime: Attentive Hierarchical Recurrent Networks for Crime Prediction. In Proceedings of the 27th ACM International Conference on Information and Knowledge Management (CIKM '18). ACM, New York, NY, USA, 1423-1432. DOI: https://doi.org/10.1145/3269206.3271793
