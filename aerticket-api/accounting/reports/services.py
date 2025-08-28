

def totalbooking_chart(date_list,final_list):
    total_booking = []
    total_booking_confirmed_count = []
    total_booking_enquiry_count = []
    total_booking_hold_count = []
    bookings_failed = []
    for ech_val in final_list:
        # print(ech_val.get('total_bookings'))
        total_booking.append(ech_val.get('total_bookings'))
        total_booking_confirmed_count.append(ech_val.get('total_booking_confirmed_count'))
        total_booking_enquiry_count.append(ech_val.get('total_booking_enquiry_count'))
        total_booking_hold_count.append(ech_val.get('total_booking_hold_count'))
        bookings_failed.append(ech_val.get('bookings_failed'))

        
        print(total_booking)
    option = {
    "tooltip": {
    "trigger": 'axis',
    "axisPointer": {
      "type": 'shadow'
    }
  },
  "legend": {},
  "grid": {
    "left": '3%',
    "right": '4%',
    "bottom": '3%',
    "containLabel": True
  },
  "xAxis": [
    {
      "type": 'category',
      "data": date_list
    }
  ],
  "yAxis": [
    {
      "type": 'value'
    }
  ],
  "series": [
    {
      "name": 'Total Bookings',
      "key": "total_bookings",
      "type": 'bar',
      "stack": 'total',
      "color": "purple",
      "emphasis": {
        "focus": 'series'
      },
      "label": {
        "show": False
      }
      
      
    },
    {
      "name": 'Total Booking Confirmed',
      "key" : 'total_booking_confirmed_count',
      "type": 'bar',
      "color": "green",
      "stack": 'total',
      "emphasis": {
        "focus": 'series'
      },
      "label": {
        "show": False
      }
     
    },
    {
      "name": 'Total Booking Enquiry',
      "key": 'total_booking_enquiry_count',
      "type": 'bar',
      "color": "orange",
      "stack": 'total',
      "emphasis": {
        "focus": 'series'
      },
      "label": {
        "show": False
      }
 
    },
    {
      "name": 'Total Booking Hold',
      "key": 'total_booking_hold_count',
      "type": 'bar',
      "color": "yellow",
      "stack": 'total',
      "emphasis": {
        "focus": 'series'
      },
      "label": {
        "show": False
      }
  
    },
    {
      "name": 'Total Booking Failed',
      "key": 'bookings_failed',
      "type": 'bar',
      "color": "red",
      "stack": 'total',
    
      "emphasis": {
        "focus": 'series'
      },
      "label": {
        "show": False
      }
    }
   
    ]

    }   
    series = option.get('series')
    for ech_series in series:
        if ech_series.get('key') == 'total_bookings':
            ech_series['data'] = total_booking
        if ech_series.get('key') == 'total_booking_confirmed_count':
            ech_series['data'] = total_booking_confirmed_count
        if ech_series.get('key') == 'total_booking_enquiry_count':
            ech_series['data'] = total_booking_enquiry_count
        if ech_series.get('key') == 'total_booking_hold_count':
            ech_series['data'] = total_booking_hold_count
        if ech_series.get('key') == 'bookings_failed':
            ech_series['data'] = bookings_failed
    return option



def staff_booking_piechart(result):
  option = {
  "legend": {
    "top": 'bottom'
  },
  "tooltip": {
    "trigger": 'item'
  },
  "toolbox": {
    "show": True,
    "feature": {
      "mark": { "show": True },
      "dataView": { "show": True, "readOnly": False },
      "restore": { "show": True },
      "saveAsImage": { "show": True }
    }
  },
  "series": [
    {
      "name": 'Nightingale Chart',
      "type": 'pie',
      "radius": [50, 250],
      "center": ['50%', '50%'],
      "roseType": 'area',
      "itemStyle": {
        "borderRadius": 8
      },
      "label": {
        "show": True,
        "position": 'center'
      },
      "data": result
    }
  ]
}
  return option


def staff_vs_amount_line_chart(date_list,data_list):
  option = {
  "xAxis": {
    "type": 'category',
    "data": date_list
  },
  "tooltip": {
    "trigger": 'axis'
  },
  "yAxis": {
    "type": 'value'
  },
  "series": [
    {
      "data": data_list,
      "type": 'line',
      "markPoint": {
        "data": [
          { "type": 'max', "name": 'Max' , "label": {"color":"red","backgroundColor":"transparent"}},
          { "type": 'min', "name": 'Min' }
        ]
      }
    }
  ]
  }
  return option

