import openmdao.api as om

from pycycle.constants import AIR_MIX
from pycycle import cea
from pycycle.cea import chem_eq
from pycycle.cea.props_rhs import PropsRHS
from pycycle.cea.props_calcs import PropsCalcs


from pycycle.cea.unit_comps import EngUnitProps



class Properties(om.Group):

    def initialize(self):
        self.options.declare('thermo', desc='thermodynamic data object', recordable=False)

    def setup(self):
        thermo = self.options['thermo']

        num_element = thermo.num_element

        self.add_subsystem('TP2ls', PropsRHS(thermo), promotes_inputs=('T', 'n', 'n_moles', 'b0'))

        ne1 = num_element+1
        self.add_subsystem('ls2t', om.LinearSystemComp(size=ne1))
        self.add_subsystem('ls2p', om.LinearSystemComp(size=ne1))

        self.add_subsystem('tp2props', PropsCalcs(thermo=thermo),
                           promotes_inputs=['n', 'n_moles', 'T', 'P'],
                           promotes_outputs=['h', 'S', 'gamma', 'Cp', 'Cv', 'rho', 'R']
                           )
        self.connect('TP2ls.lhs_TP', ['ls2t.A', 'ls2p.A'])
        self.connect('TP2ls.rhs_T', 'ls2t.b')
        self.connect('TP2ls.rhs_P', 'ls2p.b')
        self.connect('ls2t.x', 'tp2props.result_T')
        self.connect('ls2p.x', 'tp2props.result_P')


class Thermo(om.Group):

    def initialize(self):
        self.options.declare('fl_name',
                              default="flow",
                              desc='Flowstation name of the output flow variables')
        self.options.declare('mode',
                              desc='Set the computation mode for the thermodynamics',
                              default='total_TP',
                              values=('total_TP', 'total_SP', 'total_hP', 
                                    'static_MN', 'static_A', 'static_Ps'))
        # thermo_dict should be a dictionary containing all the information needed to setup
        # the thermo calculations:
        #       - For CEA this would be the elements and thermo_data
        #       - For Ideal this would be gamma, MW, h_base, T_base, Cp, S_data
        #       - For Tabular this would be the thermo data table
        # The user should define one or more of these dictionaries at the top of their model
        # then pass them into the individual componenents
        self.options.declare('thermo_dict',
                              desc='Defines the thermodynamic data to be used in computations')

    def setup(self):
        method = self.options['thermo_dict']['method']
        mode = self.options['mode']

        therm_dict = self.options['thermo_dict']

        # Instantiate components based on method for calculating the thermo properties.
        # All these components should compute the properties in a TP mode.
        if method == 'CEA':
            cea_data = cea.species_data.Thermo(therm_dict['thermo_data'], 
                                                therm_dict['elements'])

            base_thermo = chem_eq.ChemEq(thermo=cea_data, mode='T')

            in_vars = ('b0', 'T', 'P')
            out_vars = ('n', 'n_moles')
   
            

        elif method == 'Ideal':
            # base_thermo = IdealThermo(thermo_data=xx)
            pass
        elif method == 'Tabular':
            # base_thermo = TabularThermo(thermo_data=xx)
            pass

        self.add_subsystem('thermo_TP', base_thermo, 
                           promotes_inputs=in_vars, 
                           promotes_outputs=out_vars)

        # TODO: merge this into thermo_TP
        self.add_subsystem('props', Properties(thermo=cea_data),
                               promotes_inputs=('T', 'P', 'n', 'n_moles', 'b0'),
                               promotes_outputs=('gamma', 'Cp', 'Cv', 'rho', 'R','S', 'h'))

        # Add implicit components/balances to depending on the mode and connect them to
        # the properties calculation components
        # if mode == 'total_SP':
        #     bal = om.BalanceComp()
        #     bal.add_balance('T', val=500., units='degK', eq_units='cal/(g*degK)')
        # elif mode == 'total_hP':
        #     pass
        # elif mode == 'static_MN':
        #     pass
        # elif mode == 'static_A':
        #     pass
        # elif mode == 'static_Ps':
        #     pass

        # Compute English units and promote outputs to the station name
        fl_name = self.options['fl_name']
        self.add_subsystem('flow', EngUnitProps(thermo=cea_data, fl_name=fl_name),
                           promotes_inputs=('T', 'P', 'h', 'S', 'gamma', 'Cp', 'Cv', 'rho', 'n', 'n_moles', 'R', 'b0'),
                           promotes_outputs=('{}:*'.format(fl_name),))
        # Setup solver to converge thermo point

        self.set_input_defaults('P', 1, units='bar')
        self.set_input_defaults('T', 273, units='degK')


if __name__ == "__main__": 
    from pycycle.cea import species_data
    from pycycle.constants import CO2_CO_O2_MIX

    p = om.Problem()

    p.model = Thermo(mode='total_TP', 
                     thermo_dict={'method':'CEA', 
                                  'elements': {'CO':1, 'CO2':1, 'O2':1}, 
                                  'thermo_data': species_data.co2_co_o2 }
                    )

    p.setup()
    # p.final_setup()


    p.set_val('b0', [0.02272211, 0.04544422])
    p.set_val('T', 4000, units='degK')
    p.set_val('P', 1.034210, units='bar')

    p.run_model()

    p.model.list_inputs(prom_name=True, print_arrays=True)
    p.model.list_outputs(prom_name=True, print_arrays=True)

    n = p['thermo_TP.n']
    n_moles = p['thermo_TP.n_moles']

    print(n/n_moles) # [0.62003271, 0.06995092, 0.31001638]
    print(n_moles) # 0.03293137

    gamma = p['flow:gamma']
    print(gamma) # 1.19054697
