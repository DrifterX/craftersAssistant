import grequests as grq
from gevent import monkey
monkey.patch_all()
import pandas as pd
import requests as rq
from requests.exceptions import HTTPError
import random as rd
import time
from plotly import graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc ,Dash, ctx
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
from dash import dash_table as dt
import warnings
warnings.filterwarnings('ignore')

def restRequest(uRIList, maxTries = 50, currentTries = 0, multiThread = False):
    if currentTries == maxTries:
        raise Exception("Max retries reached.")
    
    if multiThread == True:
        try:
            response = (grq.get(u) for u in uRIList)
            jsonOut = []
            afterResponses = grq.map(response)
            for res in afterResponses:
                res.raise_for_status
                jsonOut.append(res.json())

        except HTTPError as http_err:
            currentTries = currentTries + 1
            time.sleep(rd.random()*10)
            print(f'http error is {http_err}')
            return restRequest(uRIList, maxTries = maxTries, currentTries = currentTries, multiThread= True)
        except Exception as err:
            currentTries = currentTries + 1
            time.sleep(rd.random()*10)
            print(f'current error {err}')
            return restRequest(uRIList, maxTries = maxTries, currentTries = currentTries, multiThread= True)

    else:
        uRI = uRIList
        try:
            response = rq.get(uRI)
            response.raise_for_status()

            jsonOut = response.json()

        except HTTPError as http_err:
            currentTries = currentTries + 1
            time.sleep(rd.random()*10)
            print(f'http error is {http_err}')
            return restRequest(uRIList, maxTries = maxTries, currentTries = currentTries, multiThread= False)
        except Exception as err:
            currentTries = currentTries + 1
            time.sleep(rd.random()*10)
            print(f'current error {err}')
            return restRequest(uRIList, maxTries = maxTries, currentTries = currentTries, multiThread= False)


    if jsonOut is None:
        jsonOut = []
        for res in afterResponses:
            jsonOut.append(res.json())
    
    return jsonOut

def getServerList(keys):

    try:
            uRI = "https://xivapi.com/servers/dc"
            jsonOut = restRequest(uRIList=uRI, maxTries= 10, multiThread=False)

    except: return

    if keys == True:
        datacenters = []
        for x in jsonOut.keys():
            datacenters.append(x)

        return datacenters
    
    return jsonOut

def listAllItems():
    try:
        uRI = ["https://xivapi.com/item"]
        jsonOut = restRequest(uRIList=uRI, maxTries=10, multiThread=False)

    except: return


def getItem(itemName):
    try:

        uRI = "https://xivapi.com/search?string=" + itemName
        jsonOut = restRequest(uRI, maxTries= 10, multiThread=False)

    except: return

    if len(jsonOut['Results']) > 2: return

    return jsonOut['Results']

def getItemByID(itemID):
    try:

        uRI = "https://xivapi.com/Item/" + str(itemID)
        jsonOut = restRequest(uRI, maxTries= 10, multiThread=False)
        
    except: return

    return jsonOut

def getRecipe(itemID, numNeeded = 1):
    try:

        uRI = "https://xivapi.com/Recipe/" + str(itemID)
        jsonOut = restRequest(uRI, maxTries= 10, multiThread=False)
        
    except: return

    itemList = []
    i = 0
    while jsonOut['AmountIngredient' + str(i)] > 0:
        if jsonOut['ItemIngredient' + str(i)]['CanBeHq'] == 1:
            rowRecipeID = getItemByID(jsonOut['ItemIngredient' + str(i)]['ID'])['Recipes'][0]['ID']
            extraRows = getRecipe(rowRecipeID, jsonOut['AmountIngredient' + str(i)])
            for xRow in extraRows:
                itemList.append(xRow)
        else:
            itemRow = {'itemName' : jsonOut['ItemIngredient' + str(i)]['Name'], 'itemID' : jsonOut['ItemIngredient' + str(i)]['ID'], 'amountNeeded' : (jsonOut['AmountIngredient' + str(i)] * numNeeded), 'numProduced' : jsonOut['AmountResult']}
            itemList.append(itemRow)
        i = i + 1

    return itemList

def getSalesHistory(recipe, weeksToGet, datacenter, currentTries = 0, maxToGet = 9001, hqOnly = False, maxTries = 1):
    secondsForWeeks = weeksToGet * 604800
    
    if type(recipe) is list:
        uRIList = []
        for num in recipe:
            uRIList.append("https://universalis.app/api/v2/history/" + str(datacenter) + "/" + str(num['itemID']) + "?entriesToReturn=" + str(maxToGet) + "&entriesWithin=" + str(secondsForWeeks))

        try:
            jsonOut = restRequest(uRIList, maxTries= 15, multiThread=True)

        except: return
        
        returnListed = []
        i = 0
        for item in jsonOut:
            for entry in item['entries']:
                if hqOnly == True and entry['hq'] == False: continue
                thisRow = entry
                thisRow['itemName'] = recipe[i]['itemName']
                thisRow['amountNeeded'] = recipe[i]['amountNeeded']

                returnListed.append(thisRow)
            
            i = i + 1
    else:
        item = recipe['itemID']
        uRI = "https://universalis.app/api/v2/history/" + str(datacenter) + "/" + str(item) + "?entriesToReturn=" + str(maxToGet) + "&entriesWithin=" + str(secondsForWeeks)
    
        try:
            jsonOut = restRequest(uRI, maxTries=15, multiThread=False)

        except: return
    
        returnListed = []
        for entry in jsonOut['entries']:
            if hqOnly == True and entry['hq'] == False: continue
            thisRow = entry
            thisRow['itemName'] = recipe['itemName']
            thisRow['amountNeeded'] = recipe['amountNeeded']

            returnListed.append(thisRow)

    return returnListed

def makeItemObject(item):
    theItemObject = {'itemName': item['Name'], 'itemID': item['ID'], 'amountNeeded': 1}
    return theItemObject

def findMean(inputDF, craftedItemName ,weeksToShow, numOfSteps, sales = 0, numRecipeOutput = 1):

    totalSeconds = weeksToShow * 604800
    firstTimestamp = inputDF['timestamp'][0]
    lastTimestamp = inputDF['timestamp'][len(inputDF) - 1]
    secondsPerStep = (firstTimestamp - lastTimestamp) / numOfSteps
    sellingPrice = []
    daySteps = (weeksToShow * 7) / numOfSteps

    for i in range(0, numOfSteps):
        beginTime = firstTimestamp - (i * secondsPerStep)
        endTime = beginTime - ((i + 1) * secondsPerStep)
        timeSlicedDF = inputDF[(inputDF['timestamp'] < beginTime) & (inputDF['timestamp'] > endTime)]
        if len(timeSlicedDF) < 1: continue
        thisRow = {}
        if sales == 1:
            thisRow['pricePerUnit'] = timeSlicedDF.groupby('itemName')['pricePerUnit'].mean().astype('int')[0]
            thisRow['totalSold'] = timeSlicedDF.groupby('itemName')['quantity'].sum().astype('int')[0]
            thisRow['timeStamp'] = timeSlicedDF.groupby('itemName')['timestamp'].mean().astype('int')[0]
            timeSlicedDF['timestamp'] = timeSlicedDF.groupby('itemName')['timestamp'].mean().astype('int')[0]
            thisRow['timeStampDT'] = pd.to_datetime(timeSlicedDF['timestamp'], unit='s')
    
        else:
            timeSlicedDF['pricePerUnit'] = round(timeSlicedDF.groupby('itemName')['pricePerUnit'].transform('mean'))
            productSlicedDF = timeSlicedDF.drop_duplicates(subset='itemName')
            productSlicedDF['modifiedPrice'] = (productSlicedDF['pricePerUnit'] * productSlicedDF['amountNeeded']) / numRecipeOutput
            thisRow['pricePerUnit'] = productSlicedDF['modifiedPrice'].sum().astype('int')

        thisRow['day'] = 1 + (i * daySteps)
        thisRow['craftedItemName'] = craftedItemName
        sellingPrice.append(thisRow)

    sellingPriceDF = pd.DataFrame(sellingPrice)
    return sellingPriceDF

def addLineToGraph(inputDF, inputFigure, showSales):
    name = inputDF['craftedItemName'][0]
    if showSales == False:
        inputFigure = inputFigure.add_trace(go.Scatter( x=inputDF['day'], 
                                                        y=inputDF['pricePerUnit'], 
                                                        name=name,
                                                        mode="lines+markers"),
                                                        secondary_y=False)

    else:
        inputFigure = inputFigure.add_trace(go.Scatter( x=inputDF['day'], 
                                                        y=inputDF['pricePerUnit'], 
                                                        name=name,
                                                        mode="lines+markers"),
                                                        secondary_y=True)
    
    return inputFigure

def addBarToGraph(inputDF, inputFigure):
    name = inputDF['craftedItemName'][0]
    inputFigure = inputFigure.add_trace(go.Bar( x=inputDF['day'],
                                                y=inputDF['totalSold'],
                                                name=name + " sales"),
                                                secondary_y=False)

    return inputFigure

def fetchSalesData(itemName, datacenter, hqOnly = True, numOfWeeks = 1):
    craftedItemData = getItem(itemName)
    craftedItemObject = makeItemObject(craftedItemData[0])
    if len(craftedItemData) == 2:
        craftedSalesHistory = getSalesHistory(craftedItemObject, numOfWeeks, datacenter, maxToGet = 99999, hqOnly = hqOnly, maxTries=25)
        craftedItemHistoryDF = pd.DataFrame(data = craftedSalesHistory)
        craftedItemHistoryDF['isCrafted'] = 1
        recipe = getRecipe(craftedItemData[1]['ID'])
        craftedItemHistoryDF['numProduced'] = recipe[0]['numProduced']

    else:
        craftedSalesHistory = getSalesHistory(craftedItemObject, numOfWeeks, datacenter, maxToGet = 99999, hqOnly = False, maxTries=25)
        craftedItemHistoryDF = pd.DataFrame(data = craftedSalesHistory)
        craftedItemHistoryDF['isCrafted'] = 0
    return craftedItemHistoryDF

def fetchSalesDataRecipe(itemName, datacenter, numOfWeeks = 1):
    craftedItemData = getItem(itemName)

    recipeID = craftedItemData[1]['ID']
    recipe = getRecipe(recipeID, 1)

    salesHistory = getSalesHistory(recipe, numOfWeeks, datacenter, maxToGet = 99999, maxTries=25)

    salesHistoryDF = pd.DataFrame(data = salesHistory)


    return salesHistoryDF

def buildLineGraph(itemDFList, matDFList, numOfHours, numOfWeeks, showMaterials = True, showSales = True):
    if showSales == True: fig = make_subplots(specs=[[{"secondary_y": True}]])
    else: fig=make_subplots()
    numOfSteps = int((168 / numOfHours) * numOfWeeks)
    for i in range(0,len(itemDFList)):
        thisListItem = findMean(itemDFList[i], itemDFList[i]['itemName'][0], numOfWeeks, numOfSteps, sales = 1)
        fig = addLineToGraph(thisListItem, fig, showSales=showSales)
        if itemDFList[i]['isCrafted'][0] == 1 and showMaterials == True:
            numOfRecipe = itemDFList[i]['numProduced'][0]
            thisList = findMean(matDFList[i], str(itemDFList[i]['itemName'][0]) + " mats", numOfWeeks, numOfSteps, numRecipeOutput= numOfRecipe)
            fig = addLineToGraph(thisList, fig, showSales=showSales)

        if showSales == True: fig = addBarToGraph(thisListItem, fig)
    
    fig.update_layout(title = dict(text="Sales of an item"))
    if showSales == True:
        fig.update_yaxes(title_text="Price in Gil", secondary_y=True)
        fig.update_yaxes(title_text="Number sold", secondary_y=False)
        fig.update_layout(
            yaxis=dict(side='right'),
            yaxis2=dict(side='left')
        )
    else: fig.update_yaxes(title_text="Price in Gil", secondary_y=False)
    return fig

def updateInfoTable(listOfItems, totalResults):
    
    theChildren = []
    i = 0
    for x in listOfItems:
        thisTimestamp = pd.to_datetime(x['timestamp'][len(x) - 1], unit='s')
        formattedTimestamp = str(thisTimestamp.date()) + "  " + str(thisTimestamp.hour) + ":" + str(thisTimestamp.minute)
        thisRow = {"itemName" : x['itemName'][0],"pricePerUnit" : x['pricePerUnit'][0], "timestamp" :formattedTimestamp, "totalResults" : totalResults[i]}
        theChildren.append(thisRow)
        i = i + 1
    
    theChildrenDF = pd.DataFrame(theChildren)
    return theChildrenDF.to_dict('records')


def updateRecipeTable(matDFList):

    theChildren = []

    for matDF in matDFList:

        beginningGroupIndex = []
        endGroupIndex = []
        eachMatName = []
        for i in matDF.groupby('itemName').groups.keys():
            eachMatName.append(i)
        
        for i in eachMatName:
            firstIndex = matDF.groupby('itemName').groups[i][0]
            lastIndex = matDF.groupby('itemName').groups[i][0] + len(matDF.groupby('itemName').groups[i]) - 1
            beginningGroupIndex.append(firstIndex)
            endGroupIndex.append(lastIndex)
        
        for i in range(0, len(beginningGroupIndex)):
            thisOldTimestamp = pd.to_datetime(matDF['timestamp'][endGroupIndex[i]], unit='s')
            formattedOldTimestamp = str(thisOldTimestamp.date()) + "  " + str(thisOldTimestamp.hour) + ":" + str(thisOldTimestamp.minute)
            thisNewTimestamp = pd.to_datetime(matDF['timestamp'][beginningGroupIndex[i]], unit='s')
            formattedNewTimestamp = str(thisNewTimestamp.date()) + "  " + str(thisNewTimestamp.hour) + ":" + str(thisNewTimestamp.minute)
            thisRow = {"itemName" : matDF['itemName'][beginningGroupIndex[i]],"numNeeded" : matDF['amountNeeded'][beginningGroupIndex[i]], 
                       "pricePerUnit" : matDF['pricePerUnit'][beginningGroupIndex[i]], "timestamp" :formattedOldTimestamp, "newTimestamp" : formattedNewTimestamp}
            theChildren.append(thisRow)

    theChildrenDF = pd.DataFrame(theChildren)
    return theChildrenDF.to_dict('records')

def updateGraph(itemDFList, matDFList, numOfHours, weeksSlider, includeMats, includeSales):
    fig = buildLineGraph(itemDFList, matDFList, numOfHours, weeksSlider, showMaterials = includeMats, showSales= includeSales)
    
    return fig


app = Dash(title= "Market board history")

servers = getServerList(keys=False)
datacenters = []

for x in servers.keys():
    datacenters.append(x)

infoTableHeaders = [{"name" : "Item Name", "id" : "itemName"},
                    {"name" : "Last Sell Price", "id" : "pricePerUnit"},
                    {"name" : "Oldest Transaction Found", "id" : "timestamp"},
                    {"name" : "Number of Transactions Found", "id" : "totalResults"}]

recipeTableHeaders = [{'name' : 'Material', 'id' : 'itemName'},
                      {'name' : 'Number needed', 'id' : 'numNeeded'},
                      {'name' : 'Last Sell Price', 'id' : 'pricePerUnit'},
                      {'name' : 'Oldest Transaction Found', 'id' : 'timestamp'},
                      {'name' : 'Latest Transaction Found', 'id' : 'newTimestamp'}]

starterGraph = make_subplots()
starterGraph.update_yaxes(title_text="Price in Gil", secondary_y=False)
starterGraph.update_layout(title = dict(text="Sales of an item"))

app.layout = html.Div([

    html.Title(['Market boards tracker']),

    html.Colgroup([
        html.Div([
            html.H4("Select Data Center and Server"),
            dcc.Dropdown(datacenters, 'Aether', id="dataCenterSelected"),
            dcc.Dropdown(id="serverList", placeholder="Select server")
        ], style={"width": "55%"}),
        html.Div([
            html.H3("Enter item names here."),
            dcc.Input(id="itemName", type="text", value="Grade 7 Tincture of Strength"),
        ]),
        html.Br(),
        html.Div([
            dcc.Input(id="secondItemName", type="text", placeholder="Enter second item name here.", value="")
        ]),
        html.Br(),
        html.Div([
            dcc.Input(id="thirdItemName", type="text", placeholder="Enter third item name here.", value="")
        ]),
        html.Br(),
        html.Div([
            dcc.Input(id="fourthItemName", type="text", placeholder="Enter fourth item name here.", value="")
        ]),
        html.Div([
            html.H3("Hours per data segment"),
            dcc.Input(id="numOfHours", type="number", value=12),
            html.H3("Show material costs"),
            dcc.RadioItems(
                ["Yes", "No"],
                "Yes",
                id="includeMats",
                inline=True
            ),
            html.H3("Show sales volume"),
            dcc.RadioItems(
                ["Yes", "No"],
                "Yes",
                id="includeSales",
                inline=True
            ),
            html.H3("Show only HQ sales"),
            dcc.RadioItems(
                ["Yes", "No"],
                "Yes",
                id="onlyHQ",
                inline=True
            )
        ])
    ], style={'width' : '20%', 'display' : 'inline-block', 'span' : 1}),

    html.Colgroup(children=[
        dcc.Graph(
            id='outputGraph',
            figure=starterGraph
        ),
        dcc.Slider(
                0.25,
                4,
                step=0.25,
                value=1,
                id="weeksSlider"
        ),
        html.H2("Number of weeks to retrieve."),
        html.Br(),
        dt.DataTable(id="infoTable", columns=infoTableHeaders),
        html.Br(),
        dt.DataTable(id="recipeTable", columns=recipeTableHeaders)
        
    ], style={'width' : '75%', 'display' : 'inline-block', 'span' : 1, 'padding' : '2px'}),

    html.Div(
        html.Button("Display Results", id='displayButton')
    )  
], style={'padding': '5px 5px'})

@app.callback(
    Output('outputGraph', 'figure'),
    Output('displayButton', 'n_clicks'),
    Output('recipeTable', 'data'),
    Output('infoTable', 'data'),
    Input('itemName', 'value'),
    Input('secondItemName', 'value'),
    Input('thirdItemName', 'value'),
    Input('fourthItemName', 'value'),
    Input('numOfHours', 'value'),
    Input('weeksSlider', 'value'),
    Input('includeMats', 'value'),
    Input('includeSales', 'value'),
    Input('onlyHQ', 'value'),
    Input('displayButton', 'n_clicks'),
    Input('dataCenterSelected', 'value'),
    Input('serverList', 'value')
)

def uponClick(itemName, secondItemName, thirdItemName, fourthItemName, numOfHours, weeksSlider, includeMats, includeSales, onlyHQ, n_clicks, dataCenterSelected, serverList):
    if n_clicks is None: raise PreventUpdate
    itemList = []
    if itemName != "": itemList.append(itemName)
    if secondItemName != "": itemList.append(secondItemName)
    if thirdItemName != "": itemList.append(thirdItemName)
    if fourthItemName != "": itemList.append(fourthItemName)

    if includeMats == "Yes": showMaterials = True
    else: showMaterials = False
    if includeSales == "Yes": showSales = True
    else: showSales = False
    if onlyHQ == "Yes": onlyReturnHQ = True
    else: onlyReturnHQ = False
    if serverList is None: returnServer = dataCenterSelected
    else: returnServer = serverList

    matDFList = []
    itemDFList = []
    totalResults = []
    for name in itemList:
        thisListDF = fetchSalesData(name, hqOnly= onlyReturnHQ, numOfWeeks= weeksSlider, datacenter = returnServer)
        totalResults.append(len(thisListDF))
        itemDFList.append(thisListDF)
        if thisListDF['isCrafted'][0] == 1 and showMaterials == True:
            thisListMatDF = fetchSalesDataRecipe(name, numOfWeeks=weeksSlider, datacenter = returnServer)
            matDFList.append(thisListMatDF)

    fig = updateGraph(itemDFList, matDFList, numOfHours, weeksSlider, showMaterials, showSales)
    infoTable = updateInfoTable(itemDFList, totalResults)
    recipeTable = updateRecipeTable(matDFList)
    return fig, None, recipeTable, infoTable

@app.callback(
    Output('serverList', 'options'),
    Input('dataCenterSelected', 'value')
)

def populateServers(dataCenterSelected):

    if dataCenterSelected != None:
        return servers[dataCenterSelected]

app.run_server(debug=True)