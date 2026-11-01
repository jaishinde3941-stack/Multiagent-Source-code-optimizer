// Category: Type Errors
// Error: Char array treated as if it can hold any string length

#include <iostream>
#include <cstring>

int main() {
    char name[5];
    
    std::cout << "Enter your name: ";
    std::cin >> name;  // ERROR: No bounds checking, can overflow
    
    std::cout << "Hello, " << name << std::endl;
    
    return 0;
}
