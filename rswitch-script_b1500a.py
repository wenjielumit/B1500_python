# -*- coding: utf-8 -*-
"""
Memristor Characterization Measurements
Programmed for Keysight B1500A

Created on 2018-11-26
Last modified on 2018-12-14

@author: 
  Kevin J. May, Ph.D.
  Laboratory for Electrochemical Interfaces
  Department of Materials Science and Engineering
  Massachusetts Institute of Technology
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import cycler
import visa
import os

###############################################################################
### User-defined measurement quantities
###############################################################################

# Channels (Use SMU #, will be converted later)
top = 3     # Top contact SMU for device
bot = 4    # Bottom common contact SMU
mater = "HfO2-NSTO"     # Film and substrate material
cond = "D450C_A500C"    # Deposition and annealing temperature
device = "FE"           # ColumnRow convention for 14x14 grid A=1, B=2, etc.
date = "20181214"       # YYYYMMDD

formcomp = 0.000005     # Current compliance during forming (A)
swcomp = 0.001         # Current compliance during switching measurement (A)

initV = 1.0             # Range for initial sweep (+- V)
finalV = [1,1.5,2]      # Ranges for final sweeps (+- V)
nswps = 5               # Number of sweep repeats for final sweeps
dVdt = 0.2              # Sweep rate (V/s) -- determines delay time
swpts = 101             # No. of IV sweep points

Vsense = 0.1            # Sensing voltage (V)
dtsense = 0.05          # Sensing timestep (s)
senspts = 200           # No. of sensing points

Vform = 3.5             # Forming voltage (V)

dVset = 0.2             # Voltage step for conductance characterization (V)
setpts = 10             # Number of voltage steps for conductance. Max/min is +/- setpts*dVset
dtset = 0.1             # Conductance set voltage timestep (s)

###############################################################################

def sweep(inst, V1, V2, npts, comp):
    hold = 0
    delay = (V2-V1)/(npts*dVdt)
    inst.write("*RST")
    inst.write("CN "+str(top)+","+str(bot)) # Enables channels. No number = enable all channels
    err = "0"
    
    # Intialize analyzer, set voltages to 0, set measurement mode
    inst.write("FMT 1,1")     # Clears buffer; specifies data format 1: ASCII 12 digits w header; mode 1: primary sweep source data
    inst.write("TSC 1")       # Enables time stamp function
    inst.write("AV 30,1")     # Averages 10 samples; 1: manual mode (not multiplied by default initial value)
    inst.write("FL 0")        # Disables filter
    inst.write("DV "+str(top)+",0,0,"+str(comp))    # Set initial voltages to zero
    inst.write("DV "+str(bot)+",0,0,"+str(comp))
    inst.write("MM 2,"+str(top))        # 2: Staircase sweep 
    inst.write("CMM "+str(top)+",1")    # 1: Compliance-side measurement
    inst.write("RI "+str(top)+",0")     # 0: Auto-range
    inst.write("WT "+str(hold)+","+str(delay))  # Set sweep hold, delay times
    inst.write("WM 1")    # Disables automatic abort when compliance reached
    err = 0
    err = int(inst.query("ERR? 1"))    # Check for errors
    if err != 0:
        inst.write("DZ")
        errorchk(inst,err)
        return
    
    # Do positive sweep
    inst.write("WV "+str(top)+",3,0,"+str(V1)+","+str(V2)+","+str(npts)+","+str(comp))  # Set sweep voltages
    inst.write("TSR")   # Clears timer
    inst.write("XE")    # Executes measurement
    inst.query("*OPC?")  # Confirms completion of previous command

    err = int(inst.query("ERR? 1"))    # Check for errors
    if err != 0:
        inst.write("DZ")
        errorchk(inst,err)
        return

#    buff = inst.query("NUB?")  # Confirms data is of expected dimensions
#    if buff != npts*6:
#        inst.write("DZ")
#        nptschk(inst,buff)

    rawdata = inst.read()   # Collects data after completion is confirmed
    rawdata = rawdata.split(',')
    
    Tdat = []
    Vdat = []
    Idat = []
    
    for i in rawdata:
        if i[2]=="I":
            Idat.append(float(i[3:]))
        if i[2]=="V":  
            Vdat.append(float(i[3:]))
        if i[2]=="T":  
            Tdat.append(float(i[3:]))

    # Will implement R = dV/dI at a later date
    
    # Do negative sweep
    inst.write("WV "+str(top)+",3,0,"+str(V1)+","+str(-V2)+","+str(npts)+","+str(comp))  # Set sweep voltages
    inst.write("XE")    # Executes measurement
    inst.query("*OPC?")  # Confirms completion of previous command

    err = int(inst.query("ERR? 1"))    # Check for errors
    if err != 0:
        inst.write("DZ")
        errorchk(inst,err)
        return

#    buff = inst.query("NUB?")  # Confirms data is of expected dimensions
#    if buff != npts*6:
#        inst.write("DZ")
#        nptschk(inst,buff)

    rawdata = inst.read()   # Collects data after completion is confirmed
    rawdata = rawdata.split(',')
    
    for i in rawdata:
        if i[2]=="I":
            Idat.append(float(i[3:]))
        if i[2]=="V":  
            Vdat.append(float(i[3:]))
        if i[2]=="T":  
            Tdat.append(float(i[3:]))
    
    inst.write("DZ;CL")     # Sets voltage to zero; disables all channels
    return [Tdat,Vdat,Idat]

def sample(inst,V,dt,npts,comp,form=False):
    inst.write("*RST")
    inst.write("CN "+str(top)+","+str(bot)) # Enables channels. No number = enable all channels
    
    inst.write("FMT 1,1")   # Clears buffer; specifies data format 1: ASCII 12 digits w header; mode 1: primary sweep source data
    inst.write("TSC 1")     # Enables time stamp function
    inst.write("FL 1")      # Enable filter
    inst.write("AAD "+str(top)+",1")    # Set ADC to high-resolution mode for each channel
    inst.write("AAD "+str(bot)+",1")
    inst.write("AIT 1,1,3") # Integration time 1: high-res ADC; 1: manual mode; 3: time = 3*80 us
    inst.write("AZ 0")      # Disable ADC zero function, which would cancels offset of high-res ADC at low V
    
    inst.write("MT 0,"+str(dt)+","+str(npts)+",0")  # Set timing of sampling measurement; hbias, dt, npts, hbase
    inst.write("MV "+str(top)+",0,0,"+str(V)+","+str(comp)) # Set SMU, vrange, base voltage, bias voltage, & compliance values
    inst.write("DV "+str(bot)+",0,0,"+str(comp))   # Set DC voltage for back contact
    err = int(inst.query("ERR? 1"))    # Check for errors
    if err != 0:
        inst.write("DZ")
        errorchk(inst,err)
        return
    
    inst.write("MM 10,"+str(top))  # Set measurement mode to sampling
    inst.write("RI "+str(top)+",0")     # Set current range
    if form==True: inst.write("MSC 2")  # Enable automatic abort during forming
    inst.write("TSR")       # Clears timer count
    inst.write("XE")
    
    inst.query("*OPC?")  # Confirms completion of previous command
    
    err = int(inst.query("ERR? 1"))    # Check for errors
    if not ((err == 0) or (err == 660)):    # Allows auto-abort error
        inst.write("DZ")
        errorchk(inst,err)
        return

#    if form==False:
#        buff = inst.query("NUB?")  # Confirms data is of expected dimensions
#        if buff != npts*3:
#            inst.write("DZ")
#            nptschk(inst,buff)
    
    rawdata = inst.read()   # Collects data after completion is confirmed
    rawdata = rawdata.split(',')
    
    Tdat = []
    Idat = []
    
    for i in rawdata:
        if i[2]=="I":
            Idat.append(float(i[3:]))
        if i[2]=="T":  
            Tdat.append(float(i[3:]))
            
    inst.write("DZ;CL")     # Sets voltage to zero; disables all channels
    return [Tdat,Idat]

def errorchk(inst,err):
    print("Instrument error: "+str(err)+" - "+inst.query("EMG? "+str(err)))
    print("Program will end.")
    return

def nptschk(inst,buff):
    return

def main():
    # Identify GPIB Resources
    rm = visa.ResourceManager()
    instflag = False
    for i in rm.list_resources():
        if "GPIB" in i:
            inst = rm.open_resource(i)
            if "B1500A" in inst.query("*IDN?"):
                instflag = True
                break
    if instflag != True: print("B1500A not found."); return
    inst.timeout = None
    inst.read_termination = '\r\n'
    
    # Convert SMU number to module channel number
    inst.write("ACH 6,2")
    inst.write("ACH 7,3") 
    inst.write("ACH 8,4")    
    inst.write("ACH 9,5")
    inst.query("*OPC?")
    
    # Set some strings for file names and headers
    outdir = "Z:/"+date+"_"+mater+"_RS/"+cond+"/"
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    sampheader = "t (s),I (A)"
    senseheader = "Sensing voltage = "+str(Vsense)+" V\n"+sampheader
    formheader = "Forming voltage = "+str(Vform)+" V\n"+sampheader
    sweepheader = "t (s),V (V),I (A)"
    
    # Initial sense
    tempdata = sample(inst,Vsense,dtsense,senspts,swcomp)
    isdata = np.transpose(np.array(tempdata))
    np.savetxt(outdir+device+"_01_initial-sens.dat", isdata, fmt='%.12e', delimiter=',', header=senseheader)
    isfig, isax = plt.subplots()
    isax.plot(tempdata[0],tempdata[1])
    isax.set_title(cond+" "+device+" Initial Sense"); isax.set_xlabel("t (s)"); isax.set_ylabel("I (A)")
    isax.ticklabel_format(axis='y',style='sci',scilimits=(0,0))
    isfig.savefig(outdir+device+"_01_initial-sens.png",dpi=300)
    
    # Initial I-V sweep
    tempdata = sweep(inst,0,initV,swpts,swcomp)
    iivdata = np.transpose(np.array(tempdata))
    np.savetxt(outdir+device+"_02_initial-iv.dat", iivdata, fmt='%.12e', delimiter=',', header=sweepheader)
    iivfig, iivax = plt.subplots()
    iivax.plot(tempdata[1],tempdata[2])
    iivax.set_title(cond+" "+device+" Initial IV"); iivax.set_xlabel("V (V)"); iivax.set_ylabel("I (A)")
    iivax.ticklabel_format(axis='y',style='sci',scilimits=(0,0))
    iivfig.savefig(outdir+device+"_02_initial-iv.png",dpi=300)

    # Forming
    tempdata = sample(inst,Vform,0.2,2400,formcomp,True)
    tempdata = np.array(tempdata)
    tempdata[tempdata >= 1e+101] = 0
    formdata = np.transpose(tempdata)
    np.savetxt(outdir+device+"_03_forming.dat", formdata, fmt='%.12e', delimiter=',', header=formheader)
    formfig, formax = plt.subplots()
    formax.plot(tempdata[0],tempdata[1])
    formax.set_title(cond+" "+device+" Forming"); formax.set_xlabel("t (s)"); formax.set_ylabel("I (A)")
    formax.ticklabel_format(axis='y',style='sci',scilimits=(0,0))
    formfig.savefig(outdir+device+"_03_forming.png",dpi=300)
    
    # Sense
    tempdata = sample(inst,Vsense,dtsense,senspts,swcomp)
    fsdata = np.transpose(np.array(tempdata))
    np.savetxt(outdir+device+"_04_form-sens.dat", fsdata, fmt='%.12e', delimiter=',', header=senseheader)
    fsfig, fsax = plt.subplots()
    fsax.plot(tempdata[0],tempdata[1])
    fsax.set_title(cond+" "+device+" Post-Forming Sense"); fsax.set_xlabel("t (s)"); fsax.set_ylabel("I (A)")
    fsax.ticklabel_format(axis='y',style='sci',scilimits=(0,0))
    fsfig.savefig(outdir+device+"_04_form-sens.png",dpi=300)
    
    # Conductance measurements
    voltages = np.linspace(dVset,dVset*setpts,setpts)
    voltages = np.append(voltages,np.linspace(-dVset,-dVset*setpts,setpts))
    Gdata = []
    setdata = []
    sensedata = []
    midpt = int(np.round(senspts/2))
    tempheader = ""
    color = plt.cm.viridis(np.linspace(0, 1,len(voltages)))
    mpl.rcParams['axes.prop_cycle'] = cycler.cycler('color',color)
    
    cfig, cax = plt.subplots(1,2, gridspec_kw = {'wspace':0.3,'hspace':0.3}, figsize=(6,3))
    cfig.suptitle(cond+" "+device, y=1.08)
    cax[0].set_title(" Conductance Set", y=1.08); cax[0].set_xlabel("t (s)"); cax[0].set_ylabel("I (A)")
    cax[1].set_title(" Conductance Sense", y=1.08); cax[1].set_xlabel("t (s)"); cax[1].set_ylabel("I (A)")
    cax[0].ticklabel_format(axis='y',style='sci',scilimits=(0,0))
    cax[1].ticklabel_format(axis='y',style='sci',scilimits=(0,0))

    for i in voltages:
        tempset = sample(inst,i,dtset,senspts,swcomp)        # Set conductance state
        setdata.append(tempset[0]); setdata.append(tempset[1])
        tempsense = sample(inst,Vsense,dtsense,senspts,swcomp)     # Sense conductance at 0.1 V
        sensedata.append(tempsense[0]); sensedata.append(tempsense[1])
        Gdata.append(np.mean(tempsense[1][midpt:])/Vsense)
        tempheader = tempheader+sampheader
        cax[0].plot(tempset[0],tempset[1])
        cax[1].plot(tempsense[0],tempsense[1])
        
    setheader = "Set voltages = "+str(voltages)+" V\n"+tempheader
    sensheader = "Sensing voltage = "+str(Vsense)+" V\n"+tempheader
    np.savetxt(outdir+device+"_05a_setcond.dat", np.transpose(np.array(setdata)),
               fmt='%.12e', delimiter=',', header=setheader)
    np.savetxt(outdir+device+"_05b_senscond.dat", np.transpose(np.array(sensedata)),
               fmt='%.12e', delimiter=',', header=sensheader,footer="Conductances: "+str(Gdata)+" Ohm^-1")
    cfig.savefig(outdir+device+"_05_cond.png",dpi=300)
    
    # Final I-V sweeps
    fivdata = []
    tempheader = ""
    
    color = plt.cm.viridis(np.linspace(0, 1,len(finalV)+1))
    mpl.rcParams['axes.prop_cycle'] = cycler.cycler('color',color)
    fivfig, fivax = plt.subplots(1,len(finalV), gridspec_kw = {'wspace':0.3,'hspace':0.3}, figsize=(9,3))
    fivfig.suptitle(cond+" "+device+" Final IV", y=1.08)
    
    for i in range(len(finalV)):
        fivax[i].set_xlabel("t (s)"); fivax[i].set_ylabel("I (A)")
        fivax[i].ticklabel_format(axis='y',style='sci',scilimits=(0,0))
    
    figindex = 0
    for Vr in finalV:        # Several ranges for sweep
        for j in range(nswps):
            tempdata = sweep(inst,0,Vr,swpts,swcomp)
            fivdata.append(tempdata[0]); fivdata.append(tempdata[1]); fivdata.append(tempdata[2])
            tempheader = tempheader+sweepheader
            fivax[figindex].plot(tempdata[1],tempdata[2])
        figindex = figindex + 1 
    np.savetxt(outdir+device+"_06_final-iv.dat", np.transpose(np.array(fivdata)),
               fmt='%.12e', delimiter=',', header=tempheader)
    fivfig.savefig(outdir+device+"_06_final-iv.png",dpi=300)
    
    print("Device measurement completed.")
    return

if __name__ == '__main__':
    main()