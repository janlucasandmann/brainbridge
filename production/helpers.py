import scipy.signal
import numpy as np
import math
import pandas as pd
import csv
from sklearn.feature_selection import SelectKBest
from sklearn.feature_selection import chi2

# Cut out extremely high or low values, as they are probably measuring errors

def removeArtifacts(data_input, events_input, upper_limit_one, upper_limit_two):
  data = []
  events = []
  u = 0

  for i in data_input:
    extreme_value_found = False
    for x in i:
      c = 0
      while c < 2:
        if c == 0:
          if x[c] == upper_limit_one:
            extreme_value_found = True
            break
          else:
            if x[c] == upper_limit_two:
              extreme_value_found = True
              break
        c += 1

    if not extreme_value_found:
        data.append(i)
        events.append(events_input[u])
        u += 1

  return data, events

# Define bandpass filter functions, which will be used to filter the data to different frequencies

def butter_bandpass(lowcut, highcut, fs, order=5):
  nyq = 0.5 * fs
  low = lowcut / nyq
  high = highcut / nyq
  sos = scipy.signal.butter(order, [low, high], analog=False, btype='band', output='sos')
  return sos

def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
  sos = butter_bandpass(lowcut, highcut, fs, order=order)
  y = scipy.signal.sosfilt(sos, data)
  return y
			
# Define Tapering function
# Each interval consists of 200 elements. The first and last elements are not as relevant as the
# elements in the middle of the interval. There are many cases, in which these marginal values are very high or low,
# which falsifies computation of mean, standard deviation, etc. This is, why tapering is needed.

w = np.hamming(200)
tapering_function = []

for i in w:
  tapering_function.append(i * 1) # --> das muss in Produktion 1x durchlaufen...  [TODO]

def applyTapering(data, zeros):
  res = []

  for x in data:
    c = 0
    res_row = []
    res_row_mini = []
    zero_list = []

    for y in x:
      for i in y:
        res_row_mini.append(i * tapering_function[c])
        
      res_row.append(res_row_mini)
      c += 1

    res.append(res_row)

  return res

# Define function for extracting features, that describe the 200 datapoints of an interval as a whole.
# This function extracts arrithmetic mean, standard deviation, the highest or lowest value of an interval (= top_val),
# the greatest differences between two datapoints on the positive and negative side (= baseline_difference_top,
# baseline_difference_bottom) and each of these values after the interval runs through a Fourier transformation.

def computeFeatures(data, temp_top_val):
  mean_row = []
  std_row = []
  temp_baseline_difference_bottom = 0
  temp_baseline_difference_top = 0

  for i in data:
    i = float(i)
    if temp_baseline_difference_bottom == 0:
      temp_baseline_difference_bottom = math.sqrt(i ** 2)
    else:
      if math.sqrt(i ** 2) < temp_baseline_difference_bottom:
        temp_baseline_difference_bottom = math.sqrt(i ** 2)
    
    if math.sqrt(i ** 2) > temp_baseline_difference_top:
      temp_baseline_difference_top = math.sqrt(i ** 2)

    if math.sqrt(i ** 2) > temp_top_val:
      temp_top_val = math.sqrt(i ** 2)
    mean_row.append(math.sqrt(i ** 2))
    std_row.append(i)

    if math.sqrt(i ** 2) > temp_top_val:
        temp_top_val = math.sqrt(i ** 2)

  return [mean_row, std_row, temp_baseline_difference_bottom, temp_baseline_difference_top, temp_top_val]

def getFeatures(lowcut, highcut, input_data):
  means = []
  std = []
  top_val = []
  temp_top_val = []
  baseline_difference = []

  # Apply fourier transform to get energy distribution on different frequencies
  means_fft = []
  std_fft = []
  top_val_fft = []
  temp_top_val_fft = []
  baseline_difference_fft = []

  #print("INPUT DATA [0][0]: ", input_data[0][0])

  for i in input_data[0][0]:
    #print("COURIOUS: ", i)
    temp_top_val.append(0)
    temp_top_val_fft.append(0)
    
  #print("FIRST EPOCH INPUT DATA: ", input_data[0])

  for epoch in input_data:
    c = 0

    means_row = []
    std_row = []
    top_val_row = []
    baseline_difference_row = []

    means_fft_row = []
    std_fft_row = []
    top_val_fft_row = []
    temp_top_val_fft_row = []
    baseline_difference_fft_row = []

    for x in np.transpose(epoch):
      
      #print("X IN EPOCH TRANSPOSED: ", x)

      filtered = butter_bandpass_filter(x - np.mean(x), lowcut=lowcut, highcut=highcut, fs=100)
      filtered_fft = np.fft.fftn(filtered)

      res = computeFeatures(filtered, temp_top_val[c])
      res_fft = computeFeatures(filtered_fft, temp_top_val_fft[c])
      
      baseline_difference_row.append(res[3] - res[2])
      baseline_difference_fft_row.append(res_fft[3] - res_fft[2])

      top_val_row.append(res[4])
      top_val_fft_row.append(res_fft[4])

      means_row.append(np.average(res[0]))
      means_fft_row.append(np.average(res_fft[0]))

      std_row.append(np.std(res[1]))
      std_fft_row.append(np.std(res_fft[1]))

      c += 1
  
    baseline_difference.append(baseline_difference_row)
    baseline_difference_fft.append(baseline_difference_fft_row)

    top_val.append(top_val_row)
    top_val_fft.append(top_val_fft_row)

    means.append(means_row)
    means_fft.append(means_fft_row)

    std.append(std_row)
    std_fft.append(std_fft_row)
    
  return [means, std, top_val, baseline_difference, means_fft, std_fft, top_val_fft, baseline_difference_fft]

# Define function to get averaged datapoints for the different event classes (in this case hand up or down).
# This will be used to measure distances between a given interval and the averaged intervals for the event classes
# to determine, which class is the nearest to the given interval.

def getAverages(data, events):
    
  # data: [ [ [x,y], [x,y], [x,y], ... ], [ [x,y], [x,y], [x,y], ... ], ... ]

  average_up = []
  average_down = []
  c = 0

  for i in data:
    if events[c] == 1:
      average_up.append(i)
    else:
      average_down.append(i)
    c += 1


  average_up_transpose = np.transpose(average_up)
  average_down_transpose = np.transpose(average_down)

  average_up_res = []
  average_down_res = []

  for sensor in average_up_transpose:
    average_up_res.append(np.average(i))
  
  for sensor in average_down_transpose:
    average_down_res.append(np.average(i))

    
  return average_up_res, average_down_res


def getAveragesMain(data):

  average = []
  average_transpose = np.transpose(data)

  average_res = []

  for sensor in average_transpose:
    average_res.append(np.average(i))
    
  return average_res

# Define functions to find extreme points in the intervals, average them for the different events and measure the distance
# from a given interval to the averaged extreme points from the different classes.

def findLocalExtremes(up, down, scaler):
  minima_up = []
  maxima_up = []
  minima_down = []
  maxima_down = []

  i = 0

  while i < len(up):
    minima_up.append(np.min(up[i:i+scaler]))
    maxima_up.append(np.max(up[i:i+scaler]))
    minima_down.append(np.min(down[i:i+scaler]))
    maxima_down.append(np.max(down[i:i+scaler]))
    i += scaler

  return minima_up, maxima_up, minima_down, maxima_down

def findLocalExtremesMain(data, scaler):
  # [[x,y], [x,y], [x,y], ...]
  minima = []
  maxima = []

  i = 0

  for i in np.transpose(data):
    minima_row, maxima_row = findLocalExtremesRow(i, scaler)
    minima.append(minima_row)
    maxima.append(maxima_row)
    

  return minima, maxima

def findLocalExtremesRow(row, scaler):
  minima = []
  maxima = []

  i = 0

  while i < len(row):
    minima.append(np.min(row[i:i+scaler]))
    maxima.append(np.max(row[i:i+scaler]))
    i += scaler

  return minima, maxima



  
def extremePointsCorrelation(data, events, scaler):

  # zuerst Sensor 1, dann Sensor 2...
  avg_up, avg_down = getAverages(data, events)
  # compute extreme points for averaged data
  minima_up, maxima_up, minima_down, maxima_down = findLocalExtremes(avg_up, avg_down, scaler)
  
  corr_res_minima = []
  corr_res_maxima = []
  minima_array = []
  maxima_array = []


  for epoch in data:
    
    corr_res_maxima_row = []
    minima_array_row = []
    maxima_array_row = []

    for i in np.transpose(epoch):
      minima, maxima = findLocalExtremesRow(i, scaler)
      minima_array_row.append(minima) # Consists of local minima per epoch --> onedimensional
      maxima_array_row.append(maxima) # Consists of local maxima per epoch --> onedimensional

    minima_array.append(minima_array_row) # Consists of local minima per epoch --> multidimensional --> Just reduced data array
    maxima_array.append(maxima_array_row) # Consists of local maxima per epoch --> multidimensional

  minima_res = []
  maxima_res = []
    
  for epoch in np.transpose(minima_array):
    c = 0
    for i in epoch:
      minima_res.append(epoch[c])
      c+=1

  for epoch in np.transpose(maxima_array):
    c = 0
    append = False

    for i in epoch:
      #if math.sqrt(np.corrcoef(i, events)[0][1] ** 2) > 0.1:
      maxima_res.append(epoch[c])
      c+=1
  

  return minima_res, maxima_res

def extremePointsCorrelationMain(data, scaler):

  minima, maxima = findLocalExtremesMain(data, scaler)

  return minima, maxima

# CORRELATIONS FOR EPOCHS AS A WHOLE

def getFrequencies(min, max, data):
	corr = []
	corr_tapered = []
	freqs = []
	i = min
	limit = max

	while i < limit - 1:
		min = i
		c = i + 1
		while c < limit:
			max = c
			corr.append(getFeatures(min, max, data))
			freqs.append([i,c])
			c += 1
		i += 1

	cores_real_numbers = []

	for frequency in corr:
		for sensor in np.transpose(frequency):
			for attribute in np.transpose(sensor):
				cores_real_numbers.append(attribute)
					
	return cores_real_numbers


def getFrequenciesPredefined(data):
  corr = []
  #data = applyTapering(data,0)

  #corr.append(getFeatures(1, 4, applyTapering(data,0)))
  #corr.append(getFeatures(8, 12, applyTapering(data,0)))
  #corr.append(getFeatures(4, 8, applyTapering(data,0)))
  #corr.append(getFeatures(12, 35, applyTapering(data,0)))
  #corr.append(getFeatures(13, 32, applyTapering(data,0)))
  corr.append(getFeatures(1, 4, data))
  corr.append(getFeatures(8, 12, data))
  corr.append(getFeatures(4, 8, data))
  corr.append(getFeatures(12, 35, data))
  corr.append(getFeatures(13, 32, data))


  cores_real_numbers = []


  for frequency in corr:
    for sensor in np.transpose(frequency):
      for attribute in np.transpose(sensor):
        cores_real_numbers.append(attribute)
					
  return cores_real_numbers



def generateTrainingSet(input_data, events):
	return pd.DataFrame(input_data), events

def write(input_data, names, subject):
    c = 0
    for i in input_data:
        title_string = subject + "-" + names[c] + ".csv"
        with open(title_string, mode='w') as file:
            file = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            file.writerow(i) 
        c += 1
        
def flatten_list(_2d_list):
    flat_list = []
    # Iterate through the outer list
    for element in _2d_list:
        # If the element is of type list, iterate through the sublist
        for item in element:
            flat_list.append(item)
            
    return flat_list
    return flat_list




def getFeaturesBasedOnCorrelation(X_reduced_res, events, GLOBAL_CORR_LIMIT_NUMBER):
    
    corr_sort_array = []
    
    c = 0
    for i in np.transpose(X_reduced_res):
        corr_sort_array.append([c, math.sqrt(np.corrcoef(i, events)[0][1] ** 2)])
        c += 1
    
    corr_sorted_array = sorted(corr_sort_array,key=lambda x: x[1])
    X_indices_real_input = corr_sorted_array[::-1]
    
    X_indices_real = np.transpose(X_indices_real_input)[0][0:GLOBAL_CORR_LIMIT_NUMBER]
        
    X_reduced_res_real = []
    
    for epoch in X_reduced_res:
        X_reduced_res_real_row = []
        c = 0
        for x in epoch:
            if c in X_indices_real:
                X_reduced_res_real_row.append(x)
            c += 1
        X_reduced_res_real.append(X_reduced_res_real_row)
        
    return X_reduced_res_real, X_indices_real



def getFeaturesBasedOnKBest(X_reduced_res, events, GLOBAL_CORR_LIMIT_NUMBER):
    
    selector = SelectKBest(chi2, k=GLOBAL_CORR_LIMIT_NUMBER)
    selector.fit(X_reduced_res, events)
    
    X_new = selector.transform(X_reduced_res)
    
    return X_new, selector.get_support(indices=True)


def generateInputData(data_raw_one, data_raw_two):
    c = 0
    data_raw = []
    
    for i in data_raw_one:
        data_raw.append([i, data_raw_two[c]])
        c += 1
        
    return data_raw


def splitData(data_raw):
    u = 0
    data_row = []
    data_split = []
    
    for i in data_raw:
        u += 1
        data_row.append(i)
        
        if u == 200:
            data_split.append(data_row)
            u = 0
            data_row = []
            
    return data_split


def reduceFeatures(input_data, X_indices):
    res = []
    
    c = 0
    for i in input_data:
        if c in X_indices:
            res.append(i)
        c += 1
            
    return res

def concatenateFeatures(cores_real_numbers, mini, maxi):
    X_reduced_res = []
    
    c = 0
    for i in np.transpose(cores_real_numbers):
        X_reduced_res_row = []
        for x in i:
            X_reduced_res_row.append(x)
        for x in np.transpose(mini)[c]:
            X_reduced_res_row.append(x)
        for x in np.transpose(maxi)[c]:
            X_reduced_res_row.append(x)
        X_reduced_res.append(X_reduced_res_row)
        c += 1
        
    
    print("VISITE 2: ", len(X_reduced_res), len(X_reduced_res[0]), len(cores_real_numbers[0]), len(np.transpose(cores_real_numbers)[0]), "MINI, MAXI: ", len(mini[0]), len(maxi[0]))
    
    return X_reduced_res
      
    

def concatenateFeaturesMain(cores_real_numbers, mini, maxi, X_indices_real):
    
    X_predict = flatten_list(cores_real_numbers)
    
    for i in mini:
        for x in i:
            X_predict.append(x)
    for i in maxi:
        for x in i:
            X_predict.append(x)
            
    print("VISITE 2: ", len(X_predict), len(cores_real_numbers), len(mini), len(maxi))

    # Reduce Features
    X_reduced_res_real = []
    c = 0
    for x in X_predict:
        if c in X_indices_real:
            X_reduced_res_real.append(x)
        c += 1
        
    return X_reduced_res_real



def evaluatePrediction(pred, evaluatePredictionIterations, evaluatePredictionThreshold):
    signal_counter = 0
    
    if len(pred) >= evaluatePredictionIterations:
        for i in pred[-evaluatePredictionIterations:]:
            if i == 1:
                signal_counter += 1
        
        if signal_counter >= evaluatePredictionThreshold: #and pred[len(pred) - 1] == 1:
            return True
        
    return False
            
            
        






    
				