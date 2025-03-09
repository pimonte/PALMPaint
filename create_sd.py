import netCDF4 as nc
from netCDF4 import Dataset
import numpy as np


def Save(data, res):
        #print("DATA", data)
        rows = [key[0] for key in data.keys()]  # Extract all row indices
        cols = [key[1] for key in data.keys()]  # Extract all column indices

        ny = max(rows) + 1  # Maximum row index + 1 gives number of rows
        nx = max(cols) + 1
        print("NX", nx)
        print("NY", ny)
        
        dx = dy = res
        
        vegetation_data = np.full((ny, nx), -1) 
        soil_data = np.full((ny, nx), -1) 
        pavement_data = np.full((ny, nx), -1)
        water_data = np.full((ny, nx), -1)
        building_id_data = np.full((ny, nx), -1)
        building_height_data = np.full((ny, nx), -1)
        building_type_data = np.full((ny, nx), -1)
        height_data = np.full((ny, nx), -1)
        
        for (row, col), metadata in data.items():
            #print(metadata)
            if "zt" in metadata and metadata["zt"] is not None:
                height_data[row, col] = metadata["zt"]
            if "vegetation_type" in metadata and metadata["vegetation_type"] is not None:
                vegetation_data[row, col] = metadata["vegetation_type"]
            if "soil_type" in metadata and metadata["soil_type"] is not None:
                soil_data[row, col] = metadata["soil_type"]
            if "pavement_type" in metadata and metadata["pavement_type"] is not None:
                pavement_data[row, col] = metadata["pavement_type"]
            if "water_type" in metadata and metadata["water_type"] is not None:
                water_data[row, col] = metadata["water_type"]
            if "building_id" in metadata and metadata["building_id"] is not None:
                building_id_data[row, col] = metadata["building_id"]
            if "building_height" in metadata and metadata["building_height"] is not None:
                building_height_data[row, col] = metadata["building_height"]
            if "building_type" in metadata and metadata["building_type"] is not None:
                building_type_data[row, col] = metadata["building_type"]
                
        # flip the data
        vegetation_data = np.flipud(vegetation_data)
        soil_data = np.flipud(soil_data)
        pavement_data = np.flipud(pavement_data)
        water_data = np.flipud(water_data)
        building_id_data = np.flipud(building_id_data)
        building_height_data = np.flipud(building_height_data)
        building_type_data = np.flipud(building_type_data)
        height_data = np.flipud(height_data)
        
                
        #print("VEGETATION", vegetation_data)
                
        print("SAVE NETCDF")
        filename = "output.nc"
        print(f"Saving to {filename}...")
        


        with (Dataset(filename, 'w', format='NETCDF4') as nc_file):

            # Define dimensions
            nc_file.createDimension('x', nx)
            nc_file.createDimension('y', ny)
            
            nc_zt = nc_file.createVariable(
            'zt', 'f4', ('y', 'x'), fill_value=-9999.0)
            nc_zt.long_name = 'terrain height'
            nc_zt.units = 'm'
            nc_zt[:, :] = nc_zt._FillValue
            
            nc_vegetation_type = nc_file.createVariable(
                'vegetation_type', 'i1', ('y', 'x'), fill_value=-127)
            nc_vegetation_type.long_name = "vegetation type classification"
            nc_vegetation_type.units = "1"
            nc_vegetation_type[:, :] = nc_vegetation_type._FillValue
            
            nc_soil_type = nc_file.createVariable(
                'soil_type', 'i1', ('y', 'x'), fill_value=-127)
            nc_soil_type.long_name = "soil type classification"
            nc_soil_type.units = "1"
            nc_soil_type.lod = np.int32(1)
            nc_soil_type[:, :] = nc_soil_type._FillValue
            
            nc_pavement_type = nc_file.createVariable(
                'pavement_type', 'i1', ('y', 'x'), fill_value=-127)
            nc_pavement_type.long_name = "pavement type classification"
            nc_pavement_type.units = "1"
            nc_pavement_type[:, :] = nc_pavement_type._FillValue
            
            nc_water_type = nc_file.createVariable(
                'water_type', 'i1', ('y', 'x'), fill_value=-127)
            nc_water_type.long_name = "water type classification"
            nc_water_type.units = "1"
            nc_water_type[:, :] = nc_water_type._FillValue
            

            
                        # Coordinates
        # -----------
            
            x = nc_file.createVariable('x', 'f4', ('x',))
            x.long_name = 'distance to origin in x-direction'
            x.units = 'm'
            x.axis = 'X'
            x[:] = np.arange(0, (nx)*dx, dx) + 0.5 * dx

            
            y = nc_file.createVariable('y', 'f4', ('y',))
            y.long_name = 'distance to origin in y-direction'
            y.units = 'm'
            y.axis = 'Y'
            y[:] = np.arange(0, (ny)*dy, dy) + 0.5 * dy
            
            
            
            # Where data is > fill_value, set the data in the NetCDF file
            nc_zt[:,:]= 0.0
            
            nc_vegetation_type[:, :] = nc_vegetation_type._FillValue
            nc_vegetation_type[:, :] = np.where(
            vegetation_data[:, :] > -1,
            vegetation_data[:, :],
            nc_vegetation_type._FillValue)
            
            nc_soil_type[:, :] = nc_soil_type._FillValue
            nc_soil_type[:, :] = np.where(
            soil_data[:, :] > -1,
            soil_data[:, :],
            nc_soil_type._FillValue)
            
            nc_pavement_type[:, :] = nc_pavement_type._FillValue
            nc_pavement_type[:, :] = np.where(
            pavement_data[:, :] > -1,
            pavement_data[:, :],
            nc_pavement_type._FillValue)
            
            nc_water_type[:, :] = nc_water_type._FillValue
            nc_water_type[:, :] = np.where(
            water_data[:, :] > -1,
            water_data[:, :],
            nc_water_type._FillValue)
            
            
            # Buildings
            if np.any(building_id_data > -1):
                print("BUILDINGS detected (switch on USM Namelist in PALM)")
                
                nc_building_id = nc_file.createVariable(
                'building_id', 'i1', ('y', 'x'), fill_value=-127)
                nc_building_id.long_name = "building ID"
                nc_building_id.units = "1"
                nc_building_id[:, :] = nc_building_id._FillValue
                
                nc_buildings_2d = nc_file.createVariable(
                'buildings_2d', 'f4', ('y', 'x'), fill_value=-9999.0)
                nc_buildings_2d.long_name = "building height"
                nc_buildings_2d.units = "m"
                nc_buildings_2d.lod = np.int32(1)
                nc_buildings_2d[:, :] = nc_buildings_2d._FillValue
                
                nc_building_type = nc_file.createVariable(
                'building_type', 'i1', ('y', 'x'), fill_value=-127)
                nc_building_type.long_name = "building type classification"
                nc_building_type.units = "1"
                nc_building_type[:, :] = nc_building_type._FillValue
                
                nc_building_id[:, :] = nc_building_id._FillValue
                nc_building_id[:, :] = np.where(
                building_id_data[:, :] > -1,
                building_id_data[:, :],
                nc_building_id._FillValue)
                
                nc_buildings_2d[:, :] = nc_buildings_2d._FillValue
                nc_buildings_2d[:, :] = np.where(
                building_height_data[:, :] > -1,
                building_height_data[:, :],
                nc_buildings_2d._FillValue)
                
                nc_building_type[:, :] = nc_building_type._FillValue
                nc_building_type[:, :] = np.where(
                building_type_data[:, :] > -1,
                building_type_data[:, :],
                nc_building_type._FillValue)
            

    
            # Add metadata
            nc_file.title = 'Idealized Scenario'
            nc_file.author = 'Your Name'
            
            nc_file.origin_lat = 52.50965  # (overwrite initialization_parameters)
            nc_file.origin_lon = 13.3139
            nc_file.origin_x = 3455249.0
            nc_file.origin_y = 5424815.0
            nc_file.origin_z = 0.0
            nc_file.rotation_angle = 0.0 

        print(f"NetCDF file saved: {filename}")