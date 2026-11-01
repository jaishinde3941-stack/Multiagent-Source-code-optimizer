// Category: Type Errors
// Error: Float to int truncation

#include <iostream>

int main() {
    double price = 99.99;
    int dollars = price;  // ERROR: Truncation, loses .99
    
    std::cout << "Original price: " << price << std::endl;
    std::cout << "Dollars: " << dollars << std::endl;
    
    return 0;
}
