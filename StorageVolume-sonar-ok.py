import oci
import pymysql 
from datetime import datetime, timedelta
import details
import database_password

def get_storage_volume_details():
    storage_list=[]   
    vm_object_id=' ' 
    availability_zone_object_id=' '
    try:
        details.logger.info("start fetching details from cmdb_ci_storage_volume")
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        identity_client = oci.identity.IdentityClient({}, signer=signer)
        compartments = identity_client.list_compartments(signer.tenancy_id,lifecycle_state='ACTIVE')
        subscribed_regions = identity_client.list_region_subscriptions(signer.tenancy_id).data
        
        region_list=[reg.region_name for reg in subscribed_regions]     
        
        
        for compartment in compartments.data:
            
                try:                    
                    for regions in region_list:
                        signer.region=regions
                        identity_client = oci.identity.IdentityClient({}, signer=signer)      
                       
                        compartment_id=compartment.id                     
                        
                        availability_domains = identity_client.list_availability_domains(compartment_id).data
                        
                        blockstorage_client = oci.core.BlockstorageClient({}, signer=signer)                       

                        list_volumes_response = blockstorage_client.list_volumes(
                            compartment_id=compartment.id
                        )     

                        volumes = list_volumes_response.data                    

                        for volume in volumes:                            
                            state=volume.lifecycle_state
                            compute_client = oci.core.ComputeClient({}, signer=signer)
                            attached_volumes_list = compute_client.list_volume_attachments(compartment_id=compartment.id,volume_id=volume.id).data
                            
                            
                            if not attached_volumes_list:                                
                                vm_object_id=' '

                            for attached_volumes in attached_volumes_list:                                                
                                if attached_volumes.lifecycle_state=='ATTACHED':   
                                    state=attached_volumes.lifecycle_state                  
                                    vm_object_id=attached_volumes.__dict__.get('_instance_id',' ')
                                    break                          
                                else:                                    
                                    vm_object_id=' '
                            
                            for availability_domain in availability_domains:
                                if volume.availability_domain==availability_domain.name:
                                    availability_zone_object_id= availability_domain.id
                                    break
                            tag=volume.defined_tags['Oracle-Tags']
                            tags=str(tag)
                            name=volume.display_name
                            object_id=volume.id                            
                            d=volume.size_in_gbs
                            d=d * 1024 * 1024 * 1024
                            size_bytes=f"{d:.5e}"
                            volume_id=volume.id
                            size_in_gbs=volume.size_in_gbs
                            availability_domain=volume.availability_domain
                            
                            storage_list.append({
                                'Name' :             name or ' ',
                                'Object_id'  :       object_id or ' ',
                                'State'  :           state or ' ',
                                'Size_bytes':        size_bytes or ' ',
                                'Volume_ID' :        volume_id or ' ',
                                "Account_id" :       compartment_id or ' ',
                                'size_in_gb':        size_in_gbs or ' ',
                                'Datacenter':        signer.region or ' ',
                                "Avalibility_zone" : availability_domain or ' ',
                                "Tags":              tags or ' ',                                 
                                "Vm_object_id"  :    vm_object_id,
                                "Availability_zone_object_id": availability_zone_object_id


                            })
                except Exception as e:
                    print(f"Account name = {compartment.name} is not authorized:", e)
        insert_storage_volume_into_db(storage_list) 
         
    except Exception as e:
        print("Error fetching volumes:", e)
  


def insert_storage_volume_into_db(storage_list):
    db_host="10.0.1.56"    
    db_user="admin"
    db_pass=database_password.get_secret_from_vault()
    db_name="oci"
    try:
        connection=pymysql.connect(host=db_host,user=db_user,password=db_pass,database=db_name,cursorclass=pymysql.cursors.DictCursor)
       
        table_name = 'cmdb_ci_storage_volume'

        cursor = connection.cursor()

        current_date = datetime.now()
        current_time = datetime.now().strftime("%H:%M:%S")
        previous_date = (current_date - timedelta(days=1)).strftime("%d-%m-%Y")

        show_table = f"SHOW TABLES LIKE '{table_name}'"
        cursor.execute(show_table)
        tb = cursor.fetchone()
        if tb:
            rename_table_query = f"ALTER TABLE `{table_name}` RENAME TO `{table_name}_{previous_date}_{current_time}`"
            cursor.execute(rename_table_query)


        create_table = """
        CREATE TABLE IF NOT EXISTS cmdb_ci_storage_volume (
            Name varchar(100),
            Object_id varchar(100),
            State varchar(50),
            Size_bytes varchar(50),
            Volume_ID varchar(100),
            Account_id varchar(100),
            Size varchar(50),
            DataCenter varchar(100),
            Avalibility_zone varchar(50),
            Tags varchar(100),
            Vm_object_id varchar(100),
            Hosts varchar(100),
            Availability_zone_object_id varchar(100)

        );"""


        cursor.execute(create_table)
    
        
        for iteam in storage_list:
            insert_query = """
                INSERT INTO cmdb_ci_storage_volume(Name,Object_id,State,Size_bytes,Volume_ID,Account_id,Size,Datacenter,Avalibility_zone,Tags,Vm_object_id,Hosts,Availability_zone_object_id) 
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
            """
        
            try:
                cursor.execute(insert_query,(iteam['Name'],iteam['Object_id'],iteam['State'],iteam['Size_bytes'],iteam['Volume_ID'],iteam['Account_id'],iteam['size_in_gb'],iteam['Datacenter'],iteam['Avalibility_zone'],iteam['Tags'],iteam['Vm_object_id'],iteam['Vm_object_id'],iteam['Availability_zone_object_id']))
                
            except pymysql.Error as e:
                print(f"Error: {e}")
        print("Data INSERT INTO cmdb_ci_storage_volume is successful")

        connection.commit()
        connection.close()
    except Exception as e:
        print(f"Error inserting data into RDS: {str(e)}")      
     
if __name__=="__main__":
    get_storage_volume_details()
