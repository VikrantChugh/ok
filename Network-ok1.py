import oci
import pymysql 
from datetime import datetime, timedelta
import database_password
import details

def get_network_details():
    details.logger.info("start fetching details from cmdb_ci_network")
    network_list=[]
    try:       
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        identity_client = oci.identity.IdentityClient({}, signer=signer)
        compartments = identity_client.list_compartments(signer.tenancy_id,lifecycle_state='ACTIVE')
        
        subscribed_regions = identity_client.list_region_subscriptions(signer.tenancy_id).data
        
        region_list=[reg.region_name for reg in subscribed_regions]        
        
        for compartment in compartments.data:
            # if compartment.lifecycle_state == "ACTIVE":  
                try: 
                    for regions in region_list:
                        signer.region=regions
                
                        network_client = oci.core.VirtualNetworkClient({}, signer=signer)
                        list_vcns_response = network_client.list_vcns(compartment_id=compartment.id)
                    
                        for network in list_vcns_response.data: 
                            network_response=network.__dict__

                            network_list.append({
                                'Display_name' :        network_response.get('_display_name',' '),
                                'State' :               network_response.get('_lifecycle_state',' '),
                                'Id'  :                 network_response.get('_id',' '),
                                'Cidr_block':           network_response.get('_cidr_block',' '),
                                'Domain_name'  :        network_response.get('_vcn_domain_name',' '),
                                'Account_id':           compartment.id or ' ',
                                'Datacenter':           signer.region or ' ',
                                'Tags' :                str(network_response.get('_defined_tags',' ').get('Oracle-Tags',' '))
                            })
                            
                except Exception as e:
                    print(f"Account name = {compartment.__dict__.get('_name',' ')} is not authorized:", e) 
        insert_network_detail_into_db(network_list)
    except Exception as e:
        print("Error fetching instance data:", e)


def insert_network_detail_into_db(network_list):
    db_host="10.0.1.56"
    # db_port=3306
    db_user="admin"
    db_pass=database_password.get_secret_from_vault()
    db_name="oci"
    
    try:
        connection=pymysql.connect(host=db_host,user=db_user,password=db_pass,database=db_name,cursorclass=pymysql.cursors.DictCursor)
        
        table_name = 'cmdb_ci_network'

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
        CREATE TABLE IF NOT EXISTS cmdb_ci_network (
            Name varchar(100),
            State varchar(20),
            Object_id varchar(100),
            Cidr varchar(20),
            Domain_name varchar(50),
            Account_ID varchar(100),
            Datacenter varchar(20),
            Tags varchar(100)

        );"""


        cursor.execute(create_table)
    
        
        for iteam in network_list:
            insert_query = """
                INSERT INTO cmdb_ci_network(Name,State,Object_id,Cidr,Domain_name,Account_id,Datacenter,Tags) 
                values(%s,%s,%s,%s,%s,%s,%s,%s);
            """
            try:
                cursor.execute(insert_query,(iteam['Display_name'],iteam['State'],iteam['Id'],iteam['Cidr_block'],iteam['Domain_name'],iteam['Account_id'],iteam['Datacenter'],iteam['Tags']))
                
            except pymysql.Error as e:
                print(f"Error: {e}")
        print("Data INSERT INTO cmdb_ci_network is successful")
        connection.commit()
        connection.close()
    except Exception as e:
        print(f"Error inserting data into RDS: {str(e)}")       

if __name__=="__main__": 
    get_network_details()
