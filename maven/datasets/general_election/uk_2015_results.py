"""
Results data for the United Kingdom's 2015 General Election.

Usage:
    >>> import maven
    >>> maven.get('general-election/UK/2015/results', data_directory='./data/')


Sources:
    - http://researchbriefings.files.parliament.uk/documents/CBP-8647/1918-2017election_results.csv

Deprecated sources:
    - http://www.electoralcommission.org.uk/__data/assets/file/0004/191650/2015-UK-general-election-data-results-WEB.zip

Notes:
    - 2015-UK-general-election-data-results-WEB.zip has a lot more detailed data.
"""

import os
from pathlib import Path

import pandas as pd

from maven import utils
from maven.datasets.general_election.base import UKResults


class UK2015Results(UKResults):
    """Handles results data for the United Kingdom's 2015 General Election."""

    def __init__(self, directory=Path("data/general-election/UK/2015/results")):
        self.directory = Path(directory)
        self.sources = [
            (
                "http://researchbriefings.files.parliament.uk/documents/CBP-8647/",
                "1918-2017election_results_by_pcon.xlsx",
            ),
        ]
        self.verbose_name = "UK 2015 General Election results"

    def process(self):
        """Process results data for the United Kingdom's 2015 General Election."""
        filename = self.sources[0][1]
        processed_results_filename = "general_election-uk-2015-results.csv"
        processed_results_location = self.directory / "processed" / processed_results_filename
        os.makedirs(self.directory / "processed", exist_ok=True)  # create directory if it doesn't exist

        # Import general election results
        print(f"Read and clean {filename}")
        parties = ["Con", "LD", "Lab", "UKIP", "Grn", "SNP", "PC", "DUP", "SF", "SDLP", "UUP", "APNI", "Other"]
        results = pd.read_excel(
            self.directory / "raw" / filename, sheet_name="2015", skiprows=4, header=None, skipfooter=19
        )
        assert results.shape == (650, 49)

        # Specify columns (spread across multiple rows in Excel)
        cols = ["", "id", "Constituency", "County", "Country/Region", "Country", "Electorate", ""]
        for party in parties:
            cols += [f"{party}_Votes", f"{party}_Voteshare", ""]
        cols += ["Total votes", "Turnout"]
        results.columns = cols

        # Some basic data quality checks
        for party in parties:
            assert (results[f"{party}_Voteshare"] - results[f"{party}_Votes"] / results["Total votes"]).sum() == 0
        assert (
            results[[f"{party}_Votes" for party in parties]].fillna(0.0).sum(axis=1) == results["Total votes"]
        ).all()
        assert ((results["Total votes"] / results["Electorate"]) == results["Turnout"]).all()

        # Drop blank columns plus those that can be calculated
        cols_to_drop = [""] + [c for c in cols if "Voteshare" in c] + ["Total votes", "Turnout"]
        results = results.drop(columns=cols_to_drop)

        # Sanitise column names
        results.columns = [utils.sanitise(c) for c in results.columns]
        results = results.rename(columns={"id": "ons_id", "country/region": "region"})
        results.columns = [c.replace("_votes", "") for c in results.columns]

        # Reshape to long
        results_long = pd.melt(
            results,
            id_vars=["ons_id", "constituency", "county", "region", "country", "electorate"],
            var_name="party",
            value_name="votes",
        )
        assert results.shape == (650, 19)
        assert results_long.shape == (650 * len(parties), 19 - len(parties) + 2)

        # Sort by (ons_id, party)
        results_long["party"] = pd.Categorical(
            results_long.party, categories=pd.Series(parties).apply(utils.sanitise), ordered=True
        )
        results_long = results_long.sort_values(["ons_id", "party"]).reset_index(drop=True)

        # Re-add total_votes & voteshare
        results_long["total_votes"] = results_long.ons_id.map(results_long.groupby("ons_id").votes.sum().astype(int))
        results_long["voteshare"] = results_long["votes"] / results_long["total_votes"]

        # Export
        print(f"Exporting dataset to {processed_results_location.resolve()}")
        results_long.to_csv(processed_results_location, index=False)
