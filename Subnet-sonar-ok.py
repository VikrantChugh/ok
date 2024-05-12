import oci
import pymysql 
from datetime import datetime, timedelta
import details
import database_password

def get_subnet_details():
    subnet_list=[]
    try:
        details.logger.info("start fetching details from cmdb_ci_cloud_subnet")
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        
       
        identity_client = oci.identity.IdentityClient({}, signer=signer)
        subscribed_regions = identity_client.list_region_subscriptions(signer.tenancy_id).data
        
        region_list=[reg.region_name for reg in subscribed_regions] 
        compartments = identity_client.list_compartments(signer.tenancy_id,lifecycle_state='ACTIVE')    
        
       
        for compartment in compartments.data:
             
                try:
                    for regions in region_list:
                        signer.region=regions
                        subnet_client = oci.core.VirtualNetworkClient({}, signer=signer)
                        list_subnets_response = subnet_client.list_subnets(compartment_id=compartment.id)

                
                        for subnet in list_subnets_response.data:
                            subnet_response=subnet.__dict__                         
                            
                            
                            subnet_list.append({
                                'Display_name' : subnet_response.get('_display_name',' '),
                                'Id'  : subnet_response.get('_id',' '),
                                'Cidr_block':subnet_response.get('_cidr_block',' '),
                                'Domain_name'  : subnet_response.get('_subnet_domain_name',' '),
                                'State'   : subnet_response.get('_lifecycle_state',' '),
                                'Account_id':compartment.id,
                                'Datacenter': signer.region,
                                'Network_object_id':subnet_response.get('_vcn_id',' '),
                                'Tags': str(subnet_response.get('_defined_tags',' ').get('Oracle-Tags',' '))

                                })
                except Exception as e:
                    print(f"Account name = {compartment.__dict__.get('_name',' ')} is not authorized:", e)
        insert_subnet(subnet_list)
      
    except Exception as e:
        print("Error fetching instance data:", e)



def insert_subnet(subnet_list):
    db_host="10.0.1.56"   
    db_user="admin"
    db_pass=database_password.get_secret_from_vault()
    db_name="oci"
    try:
        connection=pymysql.connect(host=db_host,user=db_user,password=db_pass,database=db_name,cursorclass=pymysql.cursors.DictCursor)
       
        table_name = 'cmdb_ci_cloud_subnet'

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
        CREATE TABLE IF NOT EXISTS cmdb_ci_cloud_subnet (
            Name varchar(100),
            Object_id varchar(100),
            Cidr varchar(50),
            Domain_name varchar(100),
            State varchar(50),
            Account_id varchar(100),
            Datacenter varchar(50),
            Network_object_id varchar(100),
            Tags varchar(200)

        );"""


        cursor.execute(create_table)
    
        
        for item in subnet_list:
            insert_query = """
                INSERT INTO cmdb_ci_cloud_subnet(Name,Object_id,Cidr,Domain_name,State,Account_id,Datacenter,Network_object_id,Tags) 
                values(%s,%s,%s,%s,%s,%s,%s,%s,%s);
            """
            try:
                cursor.execute(insert_query,(item['Display_name'],item['Id'],item['Cidr_block'],item['Domain_name'],item['State'],item['Account_id'],item['Datacenter'],item['Network_object_id'],item['Tags']))
                
            except pymysql.Error as e:
                print(f"Error: {e}")
        print("Data INSERT INTO cmdb_ci_cloud_subnet is successful")
        connection.commit()
        connection.close()
    except Exception as e:
        print(f"Error inserting data into RDS: {str(e)}")   


if __name__=="__main__":
    get_subnet_details()
