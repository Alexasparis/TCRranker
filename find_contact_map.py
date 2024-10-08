# Find contact map:

# This file contains functions to find the most similar TCR given an input TCR using tcrdist3. 
# 1) parse_CDR3 (anarci_output)
# 2) get_germlines (sequence)

# TCRdist
# 3) create_dataframe (alpha_outputs_list, beta_outputs_list, pdb_id_list)
# 4) add_tcr_to_dataframe (df, alpha_seq, beta_seq, tcr_name)
# 5) find_closest_tcr(df, alpha_seq, beta_seq, tcr_name)

# Levenshtein distance
# 6) parse_cdrs(alfa_anarci_output, beta_anarci_output, epitope)
# 7) calculate_sequence_distance(seq1, seq2)
# 8) compute_pairwise_distances (cdrs_alpha1, cdrs_alpha2, cdrs_beta1, cdrs_beta2, epitope1, epitope2)
# 9) compute_combined_distance(cdrs_alpha1, cdrs_beta1, epitope1, cdrs_alpha2, cdrs_beta2, epitope2)
# 10) create_distance_matrix(input_df, tcr_alpha_sequence, tcr_beta_sequence, epitope)
# 11) get_min_combined_distance(df_results)

#Import libraries
from anarci import anarci
import pandas as pd
from tcrdist.repertoire import TCRrep
import Levenshtein as lev
import os

from mapping import run_anarci
from select_nr_set import calculate_sequence_distance, extract_specific_sequences


def parse_CDR3(anarci_output):
    cdr3, seq = "", ""
    for i in anarci_output.split("\n"):
        if i and i[0] != "#" and i[0] != "/":
            parts = i.rstrip().split()
            if len(parts) >= 3:
                _, num, *residues = parts
                num = int(num)  
                res = residues[-1]  
                if res != "-":
                    seq += res
                    if 105 <= num <= 117:
                        cdr3 += res
            else:
                print(f"Línea inesperada: {parts}")
    
    return cdr3, seq
    
def get_germlines(seq:str):
    '''
    Get the VJ germlines from TCRa or TCRb sequences
    '''
    input_seq = [('seq', seq)]
    try:
        results = anarci(input_seq, scheme="imgt", output=False, assign_germline=True)
        v_gene = results[1][0][0]['germlines']['v_gene'][0][1]
        j_gene = results[1][0][0]['germlines']['j_gene'][0][1]
    except:
        v_gene = 'NA'
        j_gene = 'NA'
    return v_gene, j_gene

### TCRdist 
    
def create_dataframe(alpha_outputs, beta_outputs, pdb_ids):
    """
    Creates a DataFrame with columns for CDR3, VJ germlines, and PDB ID for multiple alpha and beta chain outputs.
    """
    data = {
        'pdb_id': [],
        'cdr3_b_aa': [],
        'v_b_gene': [],
        'j_b_gene': [],
        'cdr3_a_aa': [],
        'v_a_gene': [],
        'j_a_gene': []
    }

    for anarci_output_alpha, anarci_output_beta, pdb_id in zip(alpha_outputs, beta_outputs, pdb_ids):
        # Parse ANARCI outputs
        cdr3_a, seq_a = parse_CDR3(anarci_output_alpha)
        cdr3_b, seq_b = parse_CDR3(anarci_output_beta)
        
        # Get germlines
        v_a, j_a = get_germlines(seq_a)
        v_b, j_b = get_germlines(seq_b)
        
        # Append to the data dictionary
        data['pdb_id'].append(pdb_id)
        data['cdr3_b_aa'].append(cdr3_b)
        data['v_b_gene'].append(v_b)
        data['j_b_gene'].append(j_b)
        data['cdr3_a_aa'].append(cdr3_a)
        data['v_a_gene'].append(v_a)
        data['j_a_gene'].append(j_a)

    # Create DataFrame
    df = pd.DataFrame(data)
    return df
    
def add_tcr_to_dataframe(df, alpha_seq, beta_seq, tcr_name):
    """
    Adds TCR information to the DataFrame.
    
    Parameters:
    - df (pd.DataFrame): The DataFrame to which TCR information will be added.
    - alpha_seq (str): The TCR alpha chain sequence.
    - beta_seq (str): The TCR beta chain sequence.
    - tcr_name (str): Identifier for the input TCR.
    
    Returns:
    - pd.DataFrame: Updated DataFrame with new TCR information added.
    """
    # Generate the new pdb_id
    pdb_id = f"{tcr_name}"

    # Alpha chain
    anarci_output_alpha = run_anarci(alpha_seq, "D")
    cdr3_alpha, _ = parse_CDR3(anarci_output_alpha)
    v_gene_alpha, j_gene_alpha = get_germlines(alpha_seq)
    
    # Beta chain
    anarci_output_beta = run_anarci(beta_seq, "E")
    cdr3_beta, _ = parse_CDR3(anarci_output_beta)
    v_gene_beta, j_gene_beta = get_germlines(beta_seq)
    
    # New row as DataFrame
    new_row = pd.DataFrame({
        'pdb_id': [pdb_id],
        'cdr3_a_aa': [cdr3_alpha],
        'v_a_gene': [v_gene_alpha],
        'j_a_gene': [j_gene_alpha],
        'cdr3_b_aa': [cdr3_beta],
        'v_b_gene': [v_gene_beta],
        'j_b_gene': [j_gene_beta],
        'count': [1]
    })

    # Add the new row to the DataFrame
    df = pd.concat([df, new_row], ignore_index=True)
       
    return df

import pandas as pd
from tcrdist.repertoire import TCRrep
import pandas as pd
from tcrdist.repertoire import TCRrep

def find_closest_tcr(df, alpha_seq, beta_seq, epitope, seq_dict, tcr_name):
    """
    Finds the closest TCR to the given sequences.
    
    Parameters:
    - df (pd.DataFrame): The DataFrame containing existing TCR information.
    - alpha_seq (str): The TCR alpha chain sequence of the new TCR.
    - beta_seq (str): The TCR beta chain sequence of the new TCR.
    - epitope (str): The epitope sequence to compare against.
    - seq_dict (dict): A dictionary mapping PDB IDs to their sequences for extraction.
    - tcr_name (str): The TCR name for the new entry.
    
    Returns:
    - str: The pdb_id of the closest TCR, ensuring `tcr_name` and `pdb_id` don't match.
    """
    # Add the new TCR to the DataFrame
    df = add_tcr_to_dataframe(df, alpha_seq, beta_seq, tcr_name)

    # Extract the last row as a DataFrame (which is the newly added TCR)
    last_row = df.iloc[[-1]]

    # List to store the results
    results = []

    # Iterate over each row of the DataFrame except the last one
    for end_row in range(len(df) - 1):  # Range from 0 to the second-to-last row
        # Create a new DataFrame with the current row
        current_row = df.iloc[[end_row]]  # Current row as DataFrame
        
        # Check if the current pdb_id matches the new TCR name
        current_pdb_id = current_row['pdb_id'].values[0]  # Assuming 'pdb_id' is the column name for pdb IDs
        if current_pdb_id == tcr_name:
            continue  # Skip if the current pdb_id matches the new TCR name
        
        # Construct the path to the database file
        dir_path = os.getcwd()
        db_file_path = os.path.join(dir_path, 'TCRdist', 'alphabeta_gammadelta_db.tsv')
        
        # Create a new TCRrep for the current row
        tr_current = TCRrep(cell_df=current_row,
                            organism='human', 
                            chains=['alpha', 'beta'], 
                            compute_distances=False,
                            db_file=db_file_path)

        # Create another TCRrep for the last row
        tr_last_row = TCRrep(cell_df=last_row, 
                             organism='human', 
                             chains=['alpha', 'beta'], 
                             compute_distances=False,
                             db_file=db_file_path)

        # Calculate the distances between the current row and the last row
        tr_current.compute_rect_distances(df=tr_last_row.clone_df, df2=tr_current.clone_df)

        # Sum the distances of alpha and beta to get the global distance
        global_distances = [tr_current.rw_alpha[0][i] + tr_current.rw_beta[0][i] for i in range(len(tr_current.rw_alpha[0]))]
        
        # Add the global distances to the results list
        results.append(global_distances)
    
    # Flatten the results to get only the numbers
    flattened_results = [item[0] for item in results]

    # Find the minimum value in the list
    min_value = min(flattened_results)
    
    # Get all indices where the value is equal to the minimum value
    min_indices = [index for index, value in enumerate(flattened_results) if value == min_value]

    # Collect PDB IDs for the minimum distances
    pdb_ids_with_min_distance = []
    for index in min_indices:
        pdb_id = df.iloc[index]['pdb_id']  # Adjust 'pdb_id' to match your actual column name
        pdb_ids_with_min_distance.append(pdb_id)

    # Check for multiple PDB IDs and calculate distances to the epitope
    if len(pdb_ids_with_min_distance) > 1:
        epi_distances = []
        for pdb_id in pdb_ids_with_min_distance:
            # Ensure this function returns the correct sequence for the given PDB ID
            seq_a, seq_b, epitope1 = extract_specific_sequences(f'./pdb_files/{pdb_id}.pdb', seq_dict)  # Assuming it returns the relevant epitope sequence
            distance = calculate_sequence_distance(epitope1, epitope)  # Compare with the provided epitope
            epi_distances.append(distance)
    
        # Find the minimum distance and corresponding indices
        min_distance = min(epi_distances)
        min_indices = [index for index, dist in enumerate(epi_distances) if dist == min_distance]

        # If there are multiple indices with the same minimum distance, take the first one
        pdb_id = pdb_ids_with_min_distance[min_indices[0]]  # Select the first PDB ID with the minimum distance
    else:
        pdb_id = pdb_ids_with_min_distance[0]  # Only one pdb_id, take it
    
    return pdb_id
    
# Levenshtein distance

def parse_cdrs(alfa_anarci_output, beta_anarci_output, epitope):
    """
    Extracts CDR1, CDR2, CDR2.5, and CDR3 sequences from ANARCI output for both alpha and beta chains,
    and includes the epitope in the results.
    
    Parameters:
    - alfa_anarci_output (str): The ANARCI output containing the CDR information for the alpha chain.
    - beta_anarci_output (str): The ANARCI output containing the CDR information for the beta chain.
    - epitope (str): The epitope associated.
    
    Returns:
    - dict: A dictionary containing CDR sequences (CDR1, CDR2, CDR2.5, and CDR3), and epitope for both alpha and beta chains.
    """
    # Initialize dictionaries to store sequences
    cdrs_alpha = {'CDR1': '', 'CDR2': '', 'CDR2.5': '', 'CDR3': '', 'FullSeq': ''}
    cdrs_beta = {'CDR1': '', 'CDR2': '', 'CDR2.5': '', 'CDR3': '', 'FullSeq': ''}
    
    # Process alpha chain
    for line in alfa_anarci_output.split("\n"):
        if line and line[0] != "#" and line[0] != "/":
            parts = line.rstrip().split()
            if len(parts) >= 3:
                _, num, *residues = parts
                num = int(num)  # Position number
                res = residues[-1]  # Amino acid residue
                
                if res != "-":
                    cdrs_alpha['FullSeq'] += res
                    
                    # CDR1: Residue numbers 27-38
                    if 27 <= num <= 38:
                        cdrs_alpha['CDR1'] += res
                    
                    # CDR2: Residue numbers 56-65
                    if 56 <= num <= 65:
                        cdrs_alpha['CDR2'] += res
                    
                    # CDR2.5: Residue numbers 81-86
                    if 81 <= num <= 86:
                        cdrs_alpha['CDR2.5'] += res
                    
                    # CDR3: Residue numbers 105-117
                    if 105 <= num <= 117:
                        cdrs_alpha['CDR3'] += res
    
    # Process beta chain
    for line in beta_anarci_output.split("\n"):
        if line and line[0] != "#" and line[0] != "/":
            parts = line.rstrip().split()
            if len(parts) >= 3:
                _, num, *residues = parts
                num = int(num)  # Position number
                res = residues[-1]  # Amino acid residue
                
                if res != "-":
                    cdrs_beta['FullSeq'] += res
                    
                    # CDR1: Residue numbers 27-38
                    if 27 <= num <= 38:
                        cdrs_beta['CDR1'] += res
                    
                    # CDR2: Residue numbers 56-65
                    if 56 <= num <= 65:
                        cdrs_beta['CDR2'] += res
                    
                    # CDR2.5: Residue numbers 81-86
                    if 81 <= num <= 86:
                        cdrs_beta['CDR2.5'] += res
                    
                    # CDR3: Residue numbers 105-117
                    if 105 <= num <= 117:
                        cdrs_beta['CDR3'] += res

    # Return combined results with PDB ID and epitope
    return {
        'Alpha': cdrs_alpha,
        'Beta': cdrs_beta,
        'Epitope': epitope
    }
    

def calculate_sequence_distance(seq1, seq2):
    """
    Calculates the Levenshtein distance between two sequences.
    
    :param seq1: First sequence.
    :param seq2: Second sequence.
    :return: Levenshtein distance between seq1 and seq2.
    """
    return lev.distance(seq1, seq2)

def compute_pairwise_distances(cdrs_alpha1, cdrs_alpha2, cdrs_beta1, cdrs_beta2, epitope1, epitope2):
    """Calculate pairwise distances between sequences of two TCRs."""
    distances_alpha = []
    distances_beta = []
    distances_epitope=[]
    # Calculate pairwise distances for CDRs
    for cdr_name in ['CDR1', 'CDR2', 'CDR2.5', 'CDR3']:
        # Alpha chain
        seq1_alpha = cdrs_alpha1[cdr_name]
        seq2_alpha = cdrs_alpha2[cdr_name]
        distance_alpha = calculate_sequence_distance(seq1_alpha, seq2_alpha)
        distances_alpha.append(distance_alpha)
        
        # Beta chain
        seq1_beta = cdrs_beta1[cdr_name]
        seq2_beta = cdrs_beta2[cdr_name]
        distance_beta = calculate_sequence_distance(seq1_beta, seq2_beta)
        distances_beta.append(distance_beta)
        
    
    # Calculate pairwise distance for epitopes
    distance_epitope = calculate_sequence_distance(epitope1, epitope2)
    distances_epitope.append(distance_epitope)
    
    return distances_alpha, distances_beta, distances_epitope

def compute_combined_distance(cdrs_alpha1, cdrs_beta1, epitope1, cdrs_alpha2, cdrs_beta2, epitope2):
    """Compute a combined metric of Levenshtein distances between sequences of two TCRs."""
    distances_alpha, distances_beta, distances_epitope = compute_pairwise_distances(cdrs_alpha1, cdrs_alpha2, cdrs_beta1, cdrs_beta2, epitope1, epitope2)
    combined_distance = sum(distances_alpha+distances_beta+distances_epitope)  # Sum up all the distances for a combined score
    return distances_alpha, distances_beta, distances_epitope, combined_distance

def create_distance_matrix(input_df, tcr_alpha_sequence, tcr_beta_sequence, epitope):
    results = []

    anarci_output_alpha = run_anarci(tcr_alpha_sequence, 'alpha')
    anarci_output_beta = run_anarci(tcr_beta_sequence, 'beta')
    
    cdrs = parse_cdrs(anarci_output_alpha, anarci_output_beta, epitope)
    cdrs_alpha = cdrs['Alpha']
    cdrs_beta = cdrs['Beta']
    epitope_input = cdrs['Epitope']
    
    
    for _, row in input_df.iterrows():
        pdb_id = row['pdb_id']
        
        cdrs_alpha_row = {
            'CDR1': row['cdr1_a'],
            'CDR2': row['cdr2_a'],
            'CDR2.5': row['cdr2.5_a'],
            'CDR3': row['cdr3_a']
        }
        
        cdrs_beta_row = {
            'CDR1': row['cdr1_b'],
            'CDR2': row['cdr2_b'],
            'CDR2.5': row['cdr2.5_b'],
            'CDR3': row['cdr3_b']
        }
        
        epitope_row = row['epitope']
        
        distances_alpha, distances_beta, distances_epitope, combined_distance = compute_combined_distance(
            cdrs_alpha, cdrs_beta, epitope_input,
            cdrs_alpha_row, cdrs_beta_row, epitope_row
        )
        
        results.append({
            'pdb_id': pdb_id,
            'distance_CDR1_alpha': distances_alpha[0],
            'distance_CDR2_alpha': distances_alpha[1],
            'distance_CDR2.5_alpha': distances_alpha[2],
            'distance_CDR3_alpha': distances_alpha[3],
            'distance_CDR1_beta': distances_beta[0],
            'distance_CDR2_beta': distances_beta[1],
            'distance_CDR2.5_beta': distances_beta[2],
            'distance_CDR3_beta': distances_beta[3],
            'distance_epitope': distances_epitope[0],
            'combined_distance': combined_distance
        })
    
    results_df = pd.DataFrame(results)
    return results_df

def get_min_combined_distance(df_results):
    min_idx = df_results['combined_distance'].idxmin()
    min_row = df_results.loc[min_idx]
    min_pdb_id = min_row['pdb_id']
    return min_pdb_id


